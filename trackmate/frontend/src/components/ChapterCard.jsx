export default function ChapterCard({ title, subtitle }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      <p className="muted">{subtitle}</p>
    </div>
  );
}
