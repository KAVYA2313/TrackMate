import { Link } from "react-router-dom";
import ResultCard from "../components/ResultCard.jsx";

export default function ResultPage() {
  const result = JSON.parse(localStorage.getItem("trackmate_result") || "null");
  return (
    <div>
      <h1>Test Result</h1>
      <ResultCard result={result} />
      {result?.chapter_results && (
        <div className="card">
          <h3>Chapter Results</h3>
          <table className="table">
            <thead><tr><th>Chapter ID</th><th>Score</th><th>Status</th><th>Reminder</th></tr></thead>
            <tbody>
              {result.chapter_results.map((row) => (
                <tr key={row.chapter_id}>
                  <td>{row.chapter_id}</td><td>{row.score}%</td><td>{row.status}</td><td>{row.reminder_needed ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Link className="btn" to="/schedule">Go to Schedule</Link>
    </div>
  );
}
