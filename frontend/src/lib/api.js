export async function analyzePlan(planText, query) {
  let plan = planText;
  try {
    plan = JSON.parse(planText);
  } catch (_) {
    plan = planText;
  }

  const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

  const res = await fetch(`${apiUrl}/analyze`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ plan, query })
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }
  return res.json();
}
