import { useEffect, useRef, useState } from "react";
import API from "../api/api";

export default function NotificationBell() {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const notifiedIdsRef = useRef(new Set());

  useEffect(() => {
    fetchNotifications(true);

    const interval = setInterval(() => {
      fetchNotifications(false);
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  const fetchNotifications = async (refreshRetention = false) => {
    try {
      const res = refreshRetention
        ? await API.post("/notifications/refresh")
        : await API.get("/notifications/me");

      const data = res.data;
      const list = data.notifications || [];

      setNotifications(list);
      setUnreadCount(data.unread_count || 0);

      const firstUnread = list.find((item) => !item.is_read);

      if (firstUnread && !notifiedIdsRef.current.has(firstUnread.id)) {
        notifiedIdsRef.current.add(firstUnread.id);
        triggerBrowserNotification(firstUnread);
      }
    } catch (err) {
      console.error("Notification fetch failed:", err);
    }
  };

  const triggerBrowserNotification = (item) => {
    if (!("Notification" in window)) return;

    if (Notification.permission === "granted") {
      new Notification("TrackMate Reminder", {
        body: item.message,
      });
    } else if (Notification.permission !== "denied") {
      Notification.requestPermission();
    }
  };

  const markRead = async (id) => {
    try {
      await API.post(`/notifications/${id}/read`);
      fetchNotifications(false);
    } catch (err) {
      console.error("Mark read failed:", err);
    }
  };

  const markAllRead = async () => {
    try {
      await API.post("/notifications/read-all");
      fetchNotifications(false);
    } catch (err) {
      console.error("Mark all read failed:", err);
    }
  };

  return (
    <div className="notification-wrapper">
      <button
        className="notification-btn"
        onClick={() => setOpen((prev) => !prev)}
        title="Notifications"
      >
        <span>🔔</span>
        {unreadCount > 0 && <b>{unreadCount}</b>}
      </button>

      {open && (
        <div className="notification-dropdown">
          <div className="notification-head">
            <strong>Reminders</strong>
            {unreadCount > 0 && (
              <button onClick={markAllRead}>Mark all read</button>
            )}
          </div>

          {notifications.length === 0 ? (
            <div className="notification-empty">
              No notifications yet.
            </div>
          ) : (
            notifications.map((item) => (
              <div
                key={item.id}
                className={
                  item.is_read
                    ? "notification-item"
                    : "notification-item unread"
                }
              >
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.message}</p>
                  <small>
                    Retention {Math.round(item.retention || 0)}% · Priority{" "}
                    {Math.round(item.priority_score || 0)}
                  </small>
                </div>

                {!item.is_read && (
                  <button onClick={() => markRead(item.id)}>Done</button>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}