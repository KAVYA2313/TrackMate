export default function ScheduleCard({ item }) {
  return (
    <div className="card">
      <span className="badge">{item?.task_type || "TASK"}</span>
      <h3>Chapter ID: {item?.chapter_id}</h3>
      <p className="muted">{item?.planned_minutes} minutes · {item?.status}</p>
      <p>{item?.reason}</p>
    </div>
  );
}
