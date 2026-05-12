export default function ResultCard({ result }) {
  if (!result) return null;
  const levelClass = result.result_level === "STRONG" ? "good" : result.result_level === "AVERAGE" ? "warn" : "bad";
  return (
    <div className="card">
      <span className={`badge ${levelClass}`}>{result.result_level}</span>
      <h2>{result.percentage}%</h2>
      <p className="muted">Marks: {result.obtained_marks} / {result.total_marks}</p>
    </div>
  );
}
