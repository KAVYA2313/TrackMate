import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api/api";

export default function WholePlanPage() {
  const navigate = useNavigate();

  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const fetchPlan = async () => {
    try {
      setLoading(true);
      setError("");
      const res = await API.get("/schedule/whole-plan");
      setPlan(res.data);
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Failed to load whole plan.");
    } finally {
      setLoading(false);
    }
  };

  const generateAIPlan = async () => {
    try {
      setGenerating(true);
      setError("");
      await API.post("/schedule/generate-ai-week");
      await fetchPlan();
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Failed to generate AI plan.");
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    fetchPlan();
  }, []);

  if (loading) {
    return (
      <div className="whole-plan-page">
        <div className="whole-plan-loader">Loading weekly AI plan...</div>
      </div>
    );
  }

  return (
    <div className="whole-plan-page">
      <section className="whole-plan-hero">
        <div>
          <p className="whole-plan-kicker">OpenAI Weekly Planner</p>
          <h1>Whole Week Plan</h1>
          <p>
            Monday to Sunday AI-generated plan based on topics, missed tasks,
            retention, priority score and weak chapters.
          </p>
        </div>

        <div className="whole-plan-actions">
          <button onClick={() => navigate("/schedule")}>Back Schedule</button>
          <button onClick={generateAIPlan} disabled={generating}>
            {generating ? "Generating..." : "Regenerate AI Plan"}
          </button>
        </div>
      </section>

      {error && <div className="whole-plan-error">{error}</div>}

      <section className="whole-plan-grid">
        {(plan?.days || []).map((day) => (
          <div className="whole-day-card" key={day.date}>
            <div className="whole-day-head">
              <span>{day.weekday}</span>
              <h2>{day.date}</h2>
            </div>

            {day.tasks.length === 0 ? (
              <div className="whole-empty">No task generated.</div>
            ) : (
              <div className="whole-task-list">
                {day.tasks.map((task) => (
                  <div className="whole-task-card" key={task.id}>
                    <div className="whole-task-tags">
                      <span>{task.section}</span>
                      <span>{task.task_type}</span>
                      {task.ai_generated && <span>AI</span>}
                    </div>

                    <h3>{task.topic_name || task.title}</h3>
                    <p>{task.chapter_name}</p>

                    <div className="whole-task-meta">
                      <span>{task.planned_minutes} min</span>
                      <span>
                        {task.start_time || "--"} - {task.end_time || "--"}
                      </span>
                      <span>{task.status}</span>
                    </div>

                    {task.ai_reason && (
                      <p className="whole-ai-reason">{task.ai_reason}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </section>
    </div>
  );
}