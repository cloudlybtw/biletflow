import { t as translate } from "../lib/locale";
import { useResource } from "../lib/use-resource";
import { download } from "../lib/client";
import { State, Action } from "./live-shared";
export default function CalendarLinks({ id }) {
  const resource = useResource(`/events/${id}/calendar-links`);
  return (
    <State resource={resource}>
      {resource.data && (
        <div className="bf-panel">
          <h2>{translate("Add to calendar")}</h2>
          <Action
            perform={() => download(`/events/${id}/calendar.ics`, "event.ics")}
          >
            {translate("Download calendar file")}
          </Action>
          <a
            className="bf-outline-button"
            href={resource.data.google}
            target="_blank"
            rel="noreferrer"
          >
            {translate("Google Calendar")}
          </a>
          <a
            className="bf-outline-button"
            href={resource.data.outlook}
            target="_blank"
            rel="noreferrer"
          >
            {translate("Outlook")}
          </a>
        </div>
      )}
    </State>
  );
}
