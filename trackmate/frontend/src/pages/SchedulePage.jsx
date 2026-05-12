import { useEffect, useState } from "react";
import API from "../api/api";

export default function SchedulePage() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchScheduleDashboard();
  }, []);

  const fetchScheduleDashboard = async () => {
    try {
      setLoading(true);
      setError("");
      const res = await API.get("/schedule/dashboard");
      setDashboard(res.data);
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Failed to load schedule dashboard.");
    } finally {
      setLoading(false);
    }
  };

  const generateSchedule = async () => {
    try {
      setGenerating(true);
      setError("");
      const res = await API.post("/schedule/generate-smart");
      setDashboard(res.data.dashboard);
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Failed to generate schedule.");
    } finally {
      setGenerating(false);
    }
  };

  const toggleTask = async (taskId) => {
    try {
      await API.patch(`/schedule/task/${taskId}/toggle`);
      await fetchScheduleDashboard();
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || "Failed to update task.");
    }
  };

  const markMissed = async (taskId) => {
    try {
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

  return (
    <div className="smart-schedule-page">
      <div className="schedule-hero">
        <div>
          <p className="schedule-kicker">Smart Schedule Engine</p>
          <h1>TrackMate Smart Schedule</h1>
          <p className="schedule-subtitle">
            Yesterday progress, today&apos;s action plan, and tomorrow&apos;s next step in one dashboard.
          </p>
        </div>

        <div className="schedule-actions">
          <button onClick={generateSchedule} disabled={generating}>
            {generating ? "Generating..." : "Generate / Refresh Plan"}
          </button>
        </div>
      </div>

      {error && <div className="schedule-error">{error}</div>}

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
      </div>

      <div className="schedule-main-grid">
        <div className="schedule-left">
          <div className="schedule-section-header">
            <div>
              <h2>3-Day Smart Plan</h2>
              <p>Missed topics automatically shift forward. Completed topics stay safe.</p>
            </div>
          </div>

          <div className="day-board">
            {days.map((day) => (
              <DayColumn
                key={day.date}
                day={day}
                onToggle={toggleTask}
                onMissed={markMissed}
              />
            ))}
          </div>
        </div>

        <div className="schedule-right">
          <div className="ai-card">
            <span className="ai-badge">AI Recommendation</span>
            <h2>{recommendation.title || "Smart Suggestion"}</h2>
            <p>{recommendation.message || "Follow today’s plan and complete your pending tasks."}</p>

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

            <button onClick={generateSchedule}>
              {recommendation.action || "Review Now"}
            </button>
          </div>

          <div className="logic-card">
            <h3>How this schedule works</h3>
            <ul>
              <li>New student: topics start from Chapter 1.</li>
              <li>Missed topic: shifted to revision/catch-up.</li>
              <li>Low marks: topic becomes retest priority.</li>
              <li>Weak chapter: highest priority comes first.</li>
              <li>Completed task: tick mark saves progress.</li>
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
  return (
    <div className={`day-column ${day.label?.toLowerCase()}`}>
      <div className="day-column-header">
        <div>
          <span>{day.label}</span>
          <h3>{day.weekday}</h3>
          <p>{day.date}</p>
        </div>

        <div className="day-progress">
          {day.completed_tasks}/{day.total_tasks}
        </div>
      </div>

      <TaskSection
        title="Study Section"
        emptyText="No new study tasks."
        tasks={day.study_tasks || []}
        onToggle={onToggle}
        onMissed={onMissed}
      />

      <TaskSection
        title="Revision Section"
        emptyText="No revision tasks."
        tasks={day.revision_tasks || []}
        onToggle={onToggle}
        onMissed={onMissed}
      />
    </div>
  );
}

function TaskSection({ title, emptyText, tasks, onToggle, onMissed }) {
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
            onToggle={onToggle}
            onMissed={onMissed}
          />
        ))
      )}
    </div>
  );
}

function TaskCard({ task, onToggle, onMissed }) {
  const isCompleted = task.status === "COMPLETED";
  const isMissed = task.status === "MISSED";

  return (
    <div className={`smart-task-card ${isCompleted ? "completed" : ""} ${isMissed ? "missed" : ""}`}>
      <div className="task-top">
        <button
          className={`tick-btn ${isCompleted ? "checked" : ""}`}
          onClick={() => onToggle(task.id)}
          title="Mark complete"
        >
          {isCompleted ? "✓" : ""}
        </button>

        <div className="task-info">
          <div className="task-tags">
            <span>{task.task_type}</span>
            {task.difficulty && <span>{task.difficulty}</span>}
          </div>

          <h3>{task.topic_name || task.title}</h3>
          <p>{task.chapter_name}</p>
        </div>
      </div>

      <div className="task-meta">
        <span>{task.planned_minutes} min</span>
        {task.start_time && task.end_time && (
          <span>{task.start_time} - {task.end_time}</span>
        )}
        <span>{task.status}</span>
      </div>

      {task.reason && <p className="task-reason">{task.reason}</p>}

      {!isCompleted && !isMissed && (
        <button className="missed-btn" onClick={() => onMissed(task.id)}>
          Mark Missed
        </button>
      )}
    </div>
  );
}