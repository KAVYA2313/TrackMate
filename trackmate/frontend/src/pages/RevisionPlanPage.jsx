import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import API from "../api/api";
import RevisionCard from "../components/RevisionCard";

export default function RevisionPlanPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const topicId = params.get("topicId");

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState("");

  const fetchRevision = async (forceNew = false) => {
    try {
      if (forceNew) {
        setRegenerating(true);
      } else {
        setLoading(true);
      }

      setError("");

      const res = await API.get(`/revision/topic/${topicId}`, {
        params: { force_new: forceNew },
      });

      setData(res.data);
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Failed to load revision plan.");
    } finally {
      setLoading(false);
      setRegenerating(false);
    }
  };

  useEffect(() => {
    if (topicId) {
      fetchRevision(false);
    } else {
      setError("Topic ID missing.");
      setLoading(false);
    }
  }, [topicId]);

  if (loading) {
    return (
      <div className="revision-page">
        <div className="revision-loader">Loading AI revision plan...</div>
      </div>
    );
  }

  return (
    <div className="revision-page">
      <section className="revision-hero">
        <div>
          <p className="revision-kicker">OpenAI Revision Coach</p>
          <h1>Micro Revision Plan</h1>
          <p>
            A simple topic-wise revision plan created from your weak areas and test mistakes.
          </p>
        </div>

        <div className="revision-actions">
          <button onClick={() => navigate("/schedule")}>Back Schedule</button>
          <button onClick={() => fetchRevision(true)} disabled={regenerating}>
            {regenerating ? "Regenerating..." : "Regenerate AI Plan"}
          </button>
        </div>
      </section>

      {error && <div className="revision-error">{error}</div>}

      {data && <RevisionCard data={data} />}
    </div>
  );
}