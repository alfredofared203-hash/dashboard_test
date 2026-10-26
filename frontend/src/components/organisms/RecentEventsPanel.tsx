import { Clock3, MoreHorizontal, ChevronRight } from "lucide-react";
import { SeverityIndicator } from "@/components/atoms/SeverityIndicator";
import { SectionHeader } from "@/components/molecules/SectionHeader";
import type { RecentEvent } from "@/types/dashboard";

export interface RecentEventsPanelProps {
  events: RecentEvent[];
  onViewAll: () => void;
  emptyMessage?: string;
}

export function RecentEventsPanel({
  events,
  onViewAll,
  emptyMessage = "No recent log events are available.",
}: RecentEventsPanelProps) {
  return (
    <section className="panel events-panel">
      <SectionHeader
        title="Recent events"
        description="Latest activity across services"
        action={<button className="more-button" type="button" aria-label="More event options"><MoreHorizontal size={19} /></button>}
      />
      <div className="event-list">
        {events.length === 0 && <p className="event-detail">{emptyMessage}</p>}
        {events.map((event) => (
          <article className="event-item" key={event.time}>
            <SeverityIndicator severity={event.severity} />
            <div className="event-content">
              <div className="event-title">{event.title}</div>
              <div className="event-detail">
                {event.service && <strong>{event.service} · </strong>}
                {event.detail}
              </div>
              <div className="event-time"><Clock3 size={12} /> {event.time} UTC</div>
            </div>
          </article>
        ))}
      </div>
      <button className="events-footer" type="button" onClick={onViewAll}>
        View event log <ChevronRight size={14} />
      </button>
    </section>
  );
}
