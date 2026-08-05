import {
  PredictionInputError,
  predictOlistDelay,
  validatePredictionInput,
} from "../../../../lib/olist-model";

export async function POST(request: Request): Promise<Response> {
  try {
    const payload = await request.json();
    const input = validatePredictionInput(payload);
    const prediction = predictOlistDelay(input);
    return Response.json(prediction, {
      headers: {
        "cache-control": "no-store",
      },
    });
  } catch (error) {
    if (error instanceof PredictionInputError) {
      return Response.json(
        {
          error: "Please review the order details listed below.",
          issues: error.issues,
        },
        { status: 422 },
      );
    }
    if (error instanceof SyntaxError) {
      return Response.json(
        { error: "Request body must be valid JSON." },
        { status: 400 },
      );
    }
    console.error("Olist prediction failed", error);
    return Response.json(
      { error: "The prediction service could not score this order." },
      { status: 500 },
    );
  }
}
