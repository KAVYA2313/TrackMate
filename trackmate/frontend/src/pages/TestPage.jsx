import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api/api.js";

export default function TestPage() {
  const navigate = useNavigate();
  const test = useMemo(() => JSON.parse(localStorage.getItem("trackmate_test") || "null"), []);
  const [answers, setAnswers] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (!test) {
    return (
      <div className="empty-state">
        <h1>No test found</h1>
        <p>Generate a test first, then come back here.</p>
      </div>
    );
  }

  const totalQuestions = test.questions?.length || 0;
  const answeredCount = Object.keys(answers).length;
  const progressPercent = totalQuestions ? Math.round((answeredCount / totalQuestions) * 100) : 0;

  const submit = async () => {
    setError("");

    if (answeredCount !== totalQuestions) {
      setError(`Please answer all questions before submit. Answered ${answeredCount}/${totalQuestions}.`);
      return;
    }

    setLoading(true);

    try {
      const payload = {
        answers: test.questions.map((question) => ({
          question_id: Number(question.question_id),
          selected_answer: answers[question.question_id],
        })),
      };

      const res = await API.post(`/tests/${test.test_id}/submit`, payload);
      localStorage.setItem("trackmate_result", JSON.stringify(res.data));
      navigate("/result");
    } catch (err) {
      console.error("Submit error:", err.response?.data || err.message);
      const detail = err.response?.data?.detail;

      if (typeof detail === "string") {
        setError(detail);
      } else if (Array.isArray(detail)) {
        setError(detail.map((item) => item.msg).join(", "));
      } else {
        setError("Submit failed. Check FastAPI terminal for exact backend error.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="test-layout">
      <div className="page-hero compact">
        <div>
          <p className="eyebrow">Maths assessment</p>
          <h1>Chapter Test #{test.test_id}</h1>
          <p className="muted">Answer all questions and submit to update your retention and schedule.</p>
        </div>
        <div className="score-ring">
          <span>{progressPercent}%</span>
          <small>{answeredCount}/{totalQuestions}</small>
        </div>
      </div>

      {error && <div className="alert error">{error}</div>}

      <div className="question-list">
        {test.questions.map((q, index) => (
          <div className="question-card" key={q.question_id}>
            <div className="question-topline">
              <span className="question-number">Q{index + 1}</span>
              <span className="badge">Chapter {q.chapter_id}</span>
              <span className="badge soft">{q.difficulty || "Easy"}</span>
            </div>

            <h3>{q.question_text}</h3>

            <div className="options-grid">
              {["A", "B", "C", "D"].map((opt) => {
                const selected = answers[q.question_id] === opt;
                return (
                  <label key={opt} className={`option-card ${selected ? "selected" : ""}`}>
                    <input
                      type="radio"
                      name={`q-${q.question_id}`}
                      value={opt}
                      checked={selected}
                      onChange={() => setAnswers({ ...answers, [q.question_id]: opt })}
                    />
                    <span className="option-letter">{opt}</span>
                    <span>{q[`option_${opt.toLowerCase()}`]}</span>
                  </label>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      <div className="submit-bar">
        <div>
          <strong>{answeredCount}/{totalQuestions}</strong> questions answered
          <p className="muted small">All questions are required for correct scoring.</p>
        </div>
        <button className="btn primary" onClick={submit} disabled={loading}>
          {loading ? "Submitting..." : "Submit Test"}
        </button>
      </div>
    </div>
  );
}
