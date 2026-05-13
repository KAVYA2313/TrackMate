import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import API from "../api/api";

export default function SchedulePage() {
  const navigate = useNavigate();

  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  useEffect(() => {
    fetchScheduleDashboard();
  }, []);

  const fetchScheduleDashboard = async () => {
    try {
      setLoading(true);
      setError("");
      setSuccessMessage("");

      const res = await API.get("/schedule/dashboard");
      setDashboard(res.data);
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Failed to load schedule dashboard.");
    } finally {
      setLoading(false);
    }
  };

  const generateAISchedule = async () => {
    try {
      setGenerating(true);
      setError("");
      setSuccessMessage("");

      const res = await API.post("/schedule/generate-ai-week");

      if (res.data?.ai_used) {
        setSuccessMessage("OpenAI generated your weekly schedule successfully.");
      } else {
        setSuccessMessage("Fallback schedule generated because OpenAI was not available.");
      }

      await fetchScheduleDashboard();
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Failed to generate AI schedule.");
    } finally {
      setGenerating(false);
    }
  };

  const submitTodayPlan = async () => {
    try {
      setSubmitting(true);
      setError("");
      setSuccessMessage("");

      const res = await API.post("/schedule/submit-today");

      if (res.data?.submitted) {
        setSuccessMessage(res.data.message || "Today schedule submitted successfully.");
      } else {
        setError(res.data?.message || "Complete or mark missed all today tasks first.");
      }

      await fetchScheduleDashboard();
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Failed to submit today schedule.");
    } finally {
      setSubmitting(false);
    }
  };

  const toggleTask = async (taskId, isToday) => {
    if (!isToday) {
      setError("You can complete only today's tasks.");
      return;
    }

    try {
      setError("");
      setSuccessMessage("");

      await API.patch(`/schedule/task/${taskId}/toggle`);
      await fetchScheduleDashboard();
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Failed to update task.");
    }
  };

  const markMissed = async (taskId, isToday) => {
    if (!isToday) {
      setError("You can mark missed only today's tasks.");
      return;
    }

    try {
      setError("");
      setSuccessMessage("");

      await API.patch(`/schedule/task/${taskId}/missed`);
      await fetchScheduleDashboard();
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Failed to mark task missed.");
    }
  };

  if (loading) {
    return (
      <div className="smart-schedule-page">
        <div className="schedule-loader">Loading smart schedule...</div>
      </div>
    );
  }

  const stats = dashboard?.stats || {};
  const budget = dashboard?.budget || {};
  const recommendation = dashboard?.ai_recommendation || {};
  const days = dashboard?.days || [];
  const examCountdown = dashboard?.exam_countdown || {};

  return (
    <div className="smart-schedule-page">
      <div className="schedule-hero">
        <div>
          <p className="schedule-kicker">OpenAI Smart Schedule Engine</p>

          <h1>TrackMate Smart Schedule</h1>

          <p className="schedule-subtitle">
            AI creates your study and revision plan using topics, retention,
            priority score, missed tasks, and weak chapters.
          </p>
        </div>

        <div className="schedule-actions schedule-actions-group">
          <button onClick={generateAISchedule} disabled={generating}>
            {generating ? "AI Generating..." : "Generate AI Week Plan"}
          </button>

          <button onClick={() => navigate("/schedule/whole-plan")}>
            Whole Plan
          </button>

          <button onClick={submitTodayPlan} disabled={submitting}>
            {submitting ? "Submitting..." : "Submit Today"}
          </button>
        </div>
      </div>

      {error && <div className="schedule-error">{error}</div>}

      {successMessage && (
        <div className="schedule-success">
          {successMessage}
        </div>
      )}

      <div className="schedule-stat-grid">
  <StatCard
    label="Overall Retention"
    value={`${stats.overall_retention || 0}%`}
    note="Average memory level"
  />

  <StatCard
    label="Weak Topics"
    value={stats.weak_topics || 0}
    note="Need revision first"
  />

  <StatCard
    label="Upcoming Reviews"
    value={stats.upcoming_reviews || 0}
    note="Due today/tomorrow"
  />

  <StatCard
    label="Today Study Time"
    value={`${budget.total_minutes || 0} min`}
    note={`Study ${budget.study_minutes || 0} min • Revision ${budget.revision_minutes || 0} min`}
  />

  <StatCard
    label="Exam Days Left"
    value={`${examCountdown.exam_day_left ?? 0} days`}
    note="Countdown updates daily"
  />
</div>

      <div className="schedule-main-grid">
        <div className="schedule-left">
          <div className="schedule-section-header">
            <div>
              <h2>3-Day Smart Plan</h2>
              <p>
                Yesterday is locked, today can be completed/submitted, and
                tomorrow is only preview.
              </p>
            </div>
          </div>

          <div className="day-board">
            {days.length === 0 ? (
              <div className="empty-task">
                No schedule found. Click Generate AI Week Plan.
              </div>
            ) : (
              days.map((day) => (
                <DayColumn
                  key={day.date}
                  day={day}
                  onToggle={toggleTask}
                  onMissed={markMissed}
                />
              ))
            )}
          </div>
        </div>

        <div className="schedule-right">
          <div className="ai-card">
            <span className="ai-badge">AI Recommendation</span>

            <h2>{recommendation.title || "Smart Suggestion"}</h2>

            <p>
              {recommendation.message ||
                "Generate an AI week plan to arrange study, revision, catch-up and retest tasks."}
            </p>

            <div className="ai-metrics">
              {recommendation.retention !== undefined && (
                <span>Retention: {recommendation.retention}%</span>
              )}

              {recommendation.priority_score !== undefined && (
                <span>Priority: {recommendation.priority_score}</span>
              )}

              {recommendation.last_score !== undefined && (
                <span>Last Score: {recommendation.last_score}%</span>
              )}
            </div>

            <button onClick={generateAISchedule} disabled={generating}>
              {generating ? "Generating..." : recommendation.action || "Generate AI Plan"}
            </button>
          </div>

          <div className="logic-card">
            <h3>How AI Schedule Works</h3>

            <ul>
              <li>OpenAI receives topics, retention, priority score and missed tasks.</li>
              <li>Wrong answers are analyzed to detect exact weak topics.</li>
              <li>High priority chapters are added into revision section.</li>
              <li>New topics follow chapter and topic order.</li>
              <li>Today tasks can be ticked and submitted.</li>
              <li>AI Revision Plan explains what exactly to revise.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, note }) {
  return (
    <div className="schedule-stat-card">
      <p>{label}</p>
      <h3>{value}</h3>
      <span>{note}</span>
    </div>
  );
}

function DayColumn({ day, onToggle, onMissed }) {
  const localToday = getLocalDateString();
  const isToday = day.date === localToday;

  return (
    <div
      className={`day-column ${day.label?.toLowerCase() || ""} ${
        isToday ? "today-active" : "locked-day"
      }`}
    >
      <div className="day-column-header">
        <div>
          <span>{day.label || getDayLabel(day.date)}</span>
          <h3>{day.weekday}</h3>
          <p>{day.date}</p>
        </div>

        <div className="day-progress">
          {day.completed_tasks}/{day.total_tasks}
        </div>
      </div>

      {!isToday && (
        <div className="day-lock-note">
          {day.date < localToday ? "Past day locked" : "Preview only"}
        </div>
      )}

      {isToday && (
        <div className="day-lock-note active">
          Today active: complete or mark missed your tasks.
        </div>
      )}

      <TaskSection
        title="Study Section"
        emptyText="No new study tasks."
        tasks={day.study_tasks || []}
        dayDate={day.date}
        isToday={isToday}
        onToggle={onToggle}
        onMissed={onMissed}
      />

      <TaskSection
        title="Revision Section"
        emptyText="No revision tasks."
        tasks={day.revision_tasks || []}
        dayDate={day.date}
        isToday={isToday}
        onToggle={onToggle}
        onMissed={onMissed}
      />
    </div>
  );
}

function TaskSection({
  title,
  emptyText,
  tasks,
  dayDate,
  isToday,
  onToggle,
  onMissed,
}) {
  return (
    <div className="task-section">
      <h4>{title}</h4>

      {tasks.length === 0 ? (
        <div className="empty-task">{emptyText}</div>
      ) : (
        tasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            dayDate={dayDate}
            isToday={isToday}
            onToggle={onToggle}
            onMissed={onMissed}
          />
        ))
      )}
    </div>
  );
}

function TaskCard({ task, dayDate, isToday, onToggle, onMissed }) {
  const navigate = useNavigate();

  const isCompleted = task.status === "COMPLETED";
  const isMissed = task.status === "MISSED";
  const isLocked = !isToday;

  const openRevisionPlan = () => {
    if (!task.topic_id) return;
    navigate(`/revision-plan?topicId=${task.topic_id}`);
  };

  return (
    <div
      className={`smart-task-card ${isCompleted ? "completed" : ""} ${
        isMissed ? "missed" : ""
      } ${isLocked ? "task-locked" : ""}`}
    >
      <div className="task-top">
        {isToday ? (
          <button
            className={`tick-btn ${isCompleted ? "checked" : ""}`}
            onClick={() => onToggle(task.id, isToday)}
            title="Mark complete"
          >
            {isCompleted ? "✓" : ""}
          </button>
        ) : (
          <div className="tick-btn tick-btn-disabled" title="Locked">
            🔒
          </div>
        )}

        <div className="task-info">
          <div className="task-tags">
            <span>{task.task_type || "STUDY_NEW"}</span>

            {task.difficulty && <span>{task.difficulty}</span>}

            {task.section && <span>{task.section}</span>}

            {task.ai_generated && <span>AI</span>}
          </div>

          <h3>{task.topic_name || task.title || "Scheduled Topic"}</h3>

          <p>{task.chapter_name || "Chapter"}</p>
        </div>
      </div>

      <div className="task-meta">
        <span>{task.planned_minutes || 30} min</span>

        {task.start_time && task.end_time && (
          <span>
            {task.start_time} - {task.end_time}
          </span>
        )}

        <span>{task.status}</span>

        <span>{dayDate}</span>
      </div>

      {(task.ai_reason || task.reason) && (
        <p className="task-reason">{task.ai_reason || task.reason}</p>
      )}

      {isToday && !isCompleted && !isMissed && (
        <button
          className="missed-btn"
          onClick={() => onMissed(task.id, isToday)}
        >
          Mark Missed
        </button>
      )}

      {task.topic_id && (
        <button
          className="revision-btn"
          onClick={openRevisionPlan}
        >
          AI Revision Plan
        </button>
      )}

      {!isToday && (
        <p className="task-locked-text">
          This task is locked. Only today&apos;s tasks can be updated.
        </p>
      )}
    </div>
  );
}

function getLocalDateString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function getDayLabel(dateString) {
  const today = getLocalDateString();

  const date = new Date(`${dateString}T00:00:00`);
  const todayDate = new Date(`${today}T00:00:00`);

  const diffDays = Math.round((date - todayDate) / (1000 * 60 * 60 * 24));

  if (diffDays === -1) return "Yesterday";
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";

  return "Plan";
}