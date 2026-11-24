import { useEffect, useId, useRef, useState } from "react";
import { Loader2, MapPin, Search, X } from "lucide-react";
import { useLocale, t as translate } from "@/lib/locale";
import "./VenuePicker.css";

const ALMATY = [43.2389, 76.8897];
const searchUrl = "https://nominatim.openstreetmap.org/search";

// OpenStreetMap result -> the fields POST /venues takes.
function fromSearch(item) {
  const a = item.address || {};
  const city = a.city || a.town || a.village || a.municipality || a.state || "";
  const street = [a.road, a.house_number].filter(Boolean).join(" ");
  const name = item.name || street || item.display_name.split(",")[0] || city;
  return {
    name,
    address_line: street || item.display_name.split(",").slice(0, 2).join(","),
    city,
    country: (a.country_code || "kz").toUpperCase(),
    latitude: Number(item.lat),
    longitude: Number(item.lon),
  };
}

// Venue field: pick a saved venue or any address found on OpenStreetMap,
// then fine-tune the pin on the map. `value` is either { id, ...venue } for
// a saved venue or a new place without `id` (created on submit).
export default function VenuePicker({ venues, value, onChange }) {
  const lang = useLocale();
  const listId = useId();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [state, setState] = useState("idle"); // idle | loading | error
  const [open, setOpen] = useState(false);

  const saved = (venues || []).filter(
    (v) =>
      query.trim().length > 0 &&
      `${v.name} ${v.address_line} ${v.city}`
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
  );

  // Debounced search; Nominatim allows about one request per second.
  useEffect(() => {
    const q = query.trim();
    if (q.length < 3) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setState("loading");
      try {
        const params = new URLSearchParams({
          q,
          format: "jsonv2",
          addressdetails: "1",
          limit: "6",
          countrycodes: "kz",
          "accept-language": lang,
        });
        const response = await fetch(`${searchUrl}?${params}`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error(String(response.status));
        setResults(await response.json());
        setState("idle");
      } catch (error) {
        if (error.name !== "AbortError") setState("error");
      }
    }, 700);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, lang]);

  function choose(place) {
    onChange(place);
    setQuery("");
    setResults([]);
    setOpen(false);
  }
  const showList = open && query.trim().length > 0;

  return (
    <div className="bf-venue">
      <span className="bf-venue-label">{translate("Venue")}</span>
      <div className="bf-venue-search">
        <Search aria-hidden="true" className="bf-venue-icon" />
        <input
          type="search"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-label={translate("Search for a venue or address")}
          placeholder={translate("Search for a venue or address")}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            if (e.target.value.trim().length < 3) setResults([]);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          autoComplete="off"
        />
        {state === "loading" && (
          <Loader2 aria-hidden="true" className="bf-venue-spin" />
        )}
        {showList && (
          <ul id={listId} role="listbox" className="bf-venue-list">
            {saved.map((v) => (
              <li key={v.id} role="option" aria-selected="false">
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() =>
                    choose({
                      ...v,
                      latitude: v.latitude == null ? null : Number(v.latitude),
                      longitude:
                        v.longitude == null ? null : Number(v.longitude),
                    })
                  }
                >
                  <b>{v.name}</b>
                  <small>
                    {[v.address_line, v.city].filter(Boolean).join(", ")}
                  </small>
                </button>
              </li>
            ))}
            {results.map((item) => (
              <li key={item.place_id} role="option" aria-selected="false">
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => choose(fromSearch(item))}
                >
                  <b>{fromSearch(item).name}</b>
                  <small>{item.display_name}</small>
                </button>
              </li>
            ))}
            {!saved.length && !results.length && (
              <li className="bf-venue-empty">
                {state === "error"
                  ? translate("Address search is unavailable. Try again.")
                  : query.trim().length < 3
                    ? translate("Type at least 3 characters.")
                    : state === "loading"
                      ? translate("Searching…")
                      : translate("Nothing found. Try a street or place name.")}
              </li>
            )}
          </ul>
        )}
      </div>

      {value && (
        <div className="bf-venue-picked">
          <MapPin aria-hidden="true" />
          <div>
            {value.id ? (
              <b>{value.name}</b>
            ) : (
              <input
                className="bf-venue-name"
                aria-label={translate("Venue name")}
                value={value.name}
                maxLength={200}
                onChange={(e) => onChange({ ...value, name: e.target.value })}
              />
            )}
            <small>
              {[value.address_line, value.city].filter(Boolean).join(", ")}
            </small>
          </div>
          <button
            type="button"
            className="bf-venue-clear"
            aria-label={translate("Remove venue")}
            title={translate("Remove venue")}
            onClick={() => onChange(null)}
          >
            <X aria-hidden="true" />
          </button>
        </div>
      )}

      <VenueMap
        value={value}
        onMove={
          value && !value.id
            ? (lat, lng) =>
                onChange({ ...value, latitude: lat, longitude: lng })
            : null
        }
      />
      {value && !value.id && (
        <p className="bf-venue-hint">
          {translate("Drag the pin to the exact entrance if needed.")}
        </p>
      )}
    </div>
  );
}

// Leaflet is loaded on demand so other pages don't pay for the map.
function VenueMap({ value, onMove }) {
  const box = useRef(null);
  const map = useRef(null);
  const marker = useRef(null);
  const moveRef = useRef(onMove);
  const [leaflet, setLeaflet] = useState(null);
  useEffect(() => {
    moveRef.current = onMove;
  }, [onMove]);
  // The map is a helper: if Leaflet can't run, hide it and keep the form.
  const fail = () => {
    try {
      map.current?.remove();
    } catch {
      /* already broken */
    }
    map.current = null;
    marker.current = null;
    box.current?.classList.add("is-broken");
  };

  useEffect(() => {
    let cancelled = false;
    Promise.all([import("leaflet"), import("leaflet/dist/leaflet.css")])
      .then(([L]) => {
        if (!cancelled) setLeaflet(L.default || L);
      })
      .catch(() => box.current?.classList.add("is-broken"));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!leaflet || !box.current || map.current) return;
    try {
      map.current = leaflet
        .map(box.current, { scrollWheelZoom: false })
        .setView(ALMATY, 11);
      leaflet
        .tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution: "&copy; OpenStreetMap contributors",
        })
        .addTo(map.current);
    } catch {
      fail();
    }
    return fail;
  }, [leaflet]);

  const lat = value?.latitude == null ? null : Number(value.latitude);
  const lng = value?.longitude == null ? null : Number(value.longitude);
  const draggable = Boolean(onMove);
  useEffect(() => {
    if (!leaflet || !map.current) return;
    try {
      if (
        lat == null ||
        lng == null ||
        Number.isNaN(lat) ||
        Number.isNaN(lng)
      ) {
        marker.current?.remove();
        marker.current = null;
        return;
      }
      if (!marker.current) {
        marker.current = leaflet
          .marker([lat, lng], {
            icon: leaflet.divIcon({
              className: "bf-venue-pin",
              html: "<span></span>",
              iconSize: [28, 28],
              iconAnchor: [14, 28],
            }),
          })
          .addTo(map.current);
        marker.current.on("dragend", () => {
          const p = marker.current.getLatLng();
          moveRef.current?.(p.lat, p.lng);
        });
      } else marker.current.setLatLng([lat, lng]);
      if (draggable) marker.current.dragging?.enable();
      else marker.current.dragging?.disable();
      if (!map.current.getBounds().pad(-0.2).contains(leaflet.latLng(lat, lng)))
        map.current.setView([lat, lng], Math.max(map.current.getZoom(), 15));
    } catch {
      fail();
    }
  }, [leaflet, lat, lng, draggable]);

  return (
    <div
      ref={box}
      className="bf-venue-map"
      role="img"
      aria-label={
        value ? `${translate("Map")}: ${value.name}` : translate("Map")
      }
    />
  );
}
