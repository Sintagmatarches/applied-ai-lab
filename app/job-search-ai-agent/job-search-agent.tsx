"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import type { JobSearchResponse, PublicJob } from "../../lib/jobs";

type Profile = {
  roles: string;
  skills: string;
  location: string;
  remoteOnly: boolean;
};

type Match = {
  score: number;
  roleScore: number;
  skillScore: number;
  preferenceScore: number;
  matchedSkills: string[];
  missingSkills: string[];
};

type RankedJob = PublicJob & { match: Match };

const exampleProfile: Profile = {
  roles: "Data Analyst, AI Engineer, Analytics Engineer",
  skills: "Python, SQL, Power BI, Excel, Machine Learning, Git, Azure",
  location: "Europe",
  remoteOnly: false,
};

const STORAGE_KEY = "applied-ai-lab-job-search-v20260818-1";

function terms(value: string): string[] {
  return [...new Set(value.toLowerCase().split(/[,;/\n]+|\s{2,}/).map((term) => term.trim()).filter(Boolean))];
}

function words(value: string): string[] {
  return value.toLowerCase().split(/[^a-z0-9+#.]+/).filter((word) => word.length > 1);
}

function overlap(left: string, right: string): number {
  const a = new Set(words(left));
  const b = new Set(words(right));
  if (a.size === 0 || b.size === 0) return 0;
  return [...a].filter((word) => b.has(word)).length / a.size;
}

function scoreJob(job: PublicJob, profile: Profile): Match {
  const profileSkills = terms(profile.skills);
  const evidence = `${job.title} ${job.tags.join(" ")} ${job.description}`.toLowerCase();
  const matchedSkills = profileSkills.filter((skill) => evidence.includes(skill));
  const advertisedSkills = job.tags.filter((skill) =>
    /python|sql|power bi|tableau|excel|javascript|typescript|react|node|fastapi|docker|kubernetes|azure|aws|gcp|databricks|spark|machine learning|nlp|llm|rag|git|rest|postgres|mysql|snowflake/i.test(skill),
  );
  const missingSkills = advertisedSkills.filter(
    (skill) => !profileSkills.some((profileSkill) => skill.toLowerCase().includes(profileSkill) || profileSkill.includes(skill.toLowerCase())),
  );
  const roleScore = Math.round(Math.min(1, Math.max(...terms(profile.roles).map((role) => overlap(role, job.title)), 0)) * 35);
  const skillScore = Math.round((profileSkills.length ? matchedSkills.length / profileSkills.length : 0) * 45);
  const locationMatch = !profile.location || job.location.toLowerCase().includes(profile.location.toLowerCase()) || job.remote;
  const remoteMatch = !profile.remoteOnly || job.remote;
  const preferenceScore = (locationMatch ? 10 : 0) + (remoteMatch ? 10 : 0);
  return {
    score: Math.min(100, roleScore + skillScore + preferenceScore),
    roleScore,
    skillScore,
    preferenceScore,
    matchedSkills,
    missingSkills,
  };
}

function formatDate(value: string | null): string {
  if (!value) return "Date not stated";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value));
}

export function JobSearchAgent() {
  const [profile, setProfile] = useState(exampleProfile);
  const [query, setQuery] = useState("data analyst");
  const [location, setLocation] = useState("europe");
  const [response, setResponse] = useState<JobSearchResponse | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState<PublicJob[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [agentAnswer, setAgentAnswer] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) setSaved(JSON.parse(stored) as PublicJob[]);
      } catch {
        localStorage.removeItem(STORAGE_KEY);
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const ranked = useMemo<RankedJob[]>(() =>
    (response?.jobs ?? [])
      .map((job) => ({ ...job, match: scoreJob(job, profile) }))
      .sort((left, right) => right.match.score - left.match.score),
  [response, profile]);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    setAgentAnswer("");
    try {
      const params = new URLSearchParams({ q: query, location });
      if (profile.remoteOnly) params.set("remote", "true");
      const result = await fetch(`/api/jobs/search?${params.toString()}`);
      const body = (await result.json()) as JobSearchResponse & { error?: string };
      if (!result.ok) throw new Error(body.error || "Search failed.");
      setResponse(body);
      setSelected([]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Public sources are temporarily unavailable.");
      setResponse(null);
    } finally {
      setPending(false);
    }
  }

  function toggleSaved(job: PublicJob) {
    const next = saved.some((item) => item.id === job.id)
      ? saved.filter((item) => item.id !== job.id)
      : [...saved, job];
    setSaved(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  function toggleCompare(id: string) {
    setSelected((current) => current.includes(id)
      ? current.filter((item) => item !== id)
      : current.length < 2 ? [...current, id] : [current[1], id]);
  }

  function askAgent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const q = question.toLowerCase();
    const chosen = ranked.filter((job) => selected.includes(job.id));
    const scope = chosen.length ? chosen : ranked.slice(0, 5);
    if (!scope.length) {
      setAgentAnswer("Run a search first. The agent will only answer from retrieved vacancy evidence.");
      return;
    }
    if (/compare|difference|versus|vs\b/.test(q) && scope.length >= 2) {
      setAgentAnswer(`${scope[0].title} leads at ${scope[0].match.score}% with ${scope[0].match.matchedSkills.join(", ") || "no explicit profile-skill evidence"}. ${scope[1].title} scores ${scope[1].match.score}% and is missing ${scope[1].match.missingSkills.join(", ") || "no extracted advertised skills"}.`);
    } else if (/missing|gap|learn|skill/.test(q)) {
      const counts = new Map<string, number>();
      scope.flatMap((job) => job.match.missingSkills).forEach((skill) => counts.set(skill, (counts.get(skill) ?? 0) + 1));
      const gaps = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
      setAgentAnswer(gaps.length ? `Most repeated extracted gaps: ${gaps.map(([skill, count]) => `${skill} (${count}/${scope.length})`).join(", ")}.` : "The selected vacancies do not expose a repeated gap against the current profile skills.");
    } else if (/market|common|repeat|trend/.test(q)) {
      const counts = new Map<string, number>();
      scope.flatMap((job) => job.tags).forEach((skill) => counts.set(skill, (counts.get(skill) ?? 0) + 1));
      const common = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
      setAgentAnswer(`Across ${scope.length} cited vacancies, the most repeated extracted requirements are ${common.map(([skill, count]) => `${skill} (${count})`).join(", ") || "not stated"}.`);
    } else {
      const best = scope[0];
      setAgentAnswer(`Best current evidence-backed match: ${best.title} at ${best.company} (${best.match.score}%). Role overlap contributes ${best.match.roleScore}/35, profile-skill coverage ${best.match.skillScore}/45, and location/work-mode fit ${best.match.preferenceScore}/20.`);
    }
  }

  const cited = ranked.filter((job) => selected.includes(job.id)).length
    ? ranked.filter((job) => selected.includes(job.id))
    : ranked.slice(0, Math.min(5, ranked.length));

  return (
    <div className="jobs-workspace">
      <section className="jobs-control-panel" aria-labelledby="search-title">
        <div className="jobs-control-heading">
          <div>
            <p className="eyebrow">Live public search</p>
            <h2 id="search-title">Search and match vacancies</h2>
          </div>
          <p>Example profile · edit locally</p>
        </div>

        <div className="jobs-form-layout">
          <form className="jobs-search-form" onSubmit={search}>
            <label>
              Role or keywords
              <input value={query} maxLength={80} required onChange={(event) => setQuery(event.target.value)} />
            </label>
            <label>
              Location or region
              <input value={location} maxLength={80} onChange={(event) => setLocation(event.target.value)} placeholder="Europe, Finland, Remote…" />
            </label>
            <button type="submit" disabled={pending}>{pending ? "Searching public feeds…" : "Search public jobs"}</button>
          </form>

          <fieldset className="profile-form">
            <legend>Structured profile</legend>
            <label>
              Target roles
              <textarea value={profile.roles} onChange={(event) => setProfile({ ...profile, roles: event.target.value })} />
            </label>
            <label>
              Skills, comma separated
              <textarea value={profile.skills} onChange={(event) => setProfile({ ...profile, skills: event.target.value })} />
            </label>
            <label className="profile-location">
              Preferred region
              <input value={profile.location} onChange={(event) => setProfile({ ...profile, location: event.target.value })} />
            </label>
            <label className="check-field">
              <input type="checkbox" checked={profile.remoteOnly} onChange={(event) => setProfile({ ...profile, remoteOnly: event.target.checked })} />
              Remote only
            </label>
          </fieldset>
        </div>
      </section>

      {error && <div className="jobs-error" role="alert"><strong>Search unavailable.</strong> {error}</div>}

      {response && (
        <section className="jobs-results" aria-labelledby="results-title">
          <div className="jobs-results-heading">
            <div>
              <p className="eyebrow">Normalized + deduplicated</p>
              <h2 id="results-title">{ranked.length} public vacancies</h2>
            </div>
            <div className="source-status" aria-label="Source status">
              {response.sources.map((source) => <a key={source.name} href={source.url} target="_blank" rel="noreferrer" className={source.status === "ok" ? "is-ok" : "is-down"}>{source.name} · {source.status === "ok" ? `${source.count} matched` : "unavailable"}</a>)}
              <span>{response.duplicateCount} duplicates removed</span>
              <span>Fetched {formatDate(response.retrievedAt)}</span>
            </div>
          </div>

          {ranked.length === 0 ? (
            <p className="jobs-empty">No public listing matched these filters. Broaden the role or location and search again.</p>
          ) : (
            <div className="jobs-results-layout">
              <div className="job-list">
                {ranked.map((job) => {
                  const isSaved = saved.some((item) => item.id === job.id);
                  const isSelected = selected.includes(job.id);
                  return (
                    <article className="job-card" key={job.id}>
                      <div className="job-card-top">
                        <div>
                          <p>{job.company}</p>
                          <h3>{job.title}</h3>
                          <div className="job-meta"><span>{job.location}</span><span>{job.remote ? "Remote available" : "On-site / hybrid"}</span><span>{job.employmentType}</span><span>{formatDate(job.publishedAt)}</span></div>
                        </div>
                        <div className="match-score" aria-label={`${job.match.score} percent match`}><strong>{job.match.score}%</strong><span>match</span></div>
                      </div>
                      <div className="match-breakdown"><span>Role {job.match.roleScore}/35</span><span>Skills {job.match.skillScore}/45</span><span>Preferences {job.match.preferenceScore}/20</span></div>
                      <p className="job-description">{job.description.slice(0, 310)}{job.description.length > 310 ? "…" : ""}</p>
                      <div className="job-evidence">
                        <div><strong>Matched</strong><p>{job.match.matchedSkills.join(" · ") || "No explicit profile-skill match extracted"}</p></div>
                        <div><strong>Missing / not in profile</strong><p>{job.match.missingSkills.join(" · ") || "No explicit gap extracted"}</p></div>
                      </div>
                      <footer className="job-card-actions">
                        <a href={job.url} target="_blank" rel="noreferrer">Open original ↗</a>
                        <span>Source: <a href={job.sourceUrl} target="_blank" rel="noreferrer">{job.source}</a></span>
                        <button type="button" onClick={() => toggleCompare(job.id)} className={isSelected ? "is-selected" : ""}>{isSelected ? "Selected" : "Compare"}</button>
                        <button type="button" onClick={() => toggleSaved(job)}>{isSaved ? "Saved locally" : "Save locally"}</button>
                      </footer>
                    </article>
                  );
                })}
              </div>

              <aside className="evidence-agent">
                <p className="eyebrow">Evidence agent</p>
                <h3>Ask the retrieved jobs</h3>
                <p>Try “What should I learn?”, “Compare selected jobs” or “What skills repeat?”</p>
                <form onSubmit={askAgent}>
                  <textarea value={question} required onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about the current evidence…" />
                  <button type="submit">Run agent tools</button>
                </form>
                {agentAnswer && <div className="agent-answer" aria-live="polite"><strong>Grounded answer</strong><p>{agentAnswer}</p><small>Tools: filter_results → aggregate_requirements → rank_matches</small><ol>{cited.map((job) => <li key={job.id}><a href={job.url} target="_blank" rel="noreferrer">{job.title} · {job.company}</a></li>)}</ol></div>}
                <div className="saved-summary"><strong>{saved.length}</strong><span>vacancies saved in this browser</span></div>
              </aside>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
