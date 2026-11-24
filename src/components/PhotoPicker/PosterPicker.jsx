import { useEffect, useRef, useState } from "react";
import { ImageUp, RefreshCw, Trash2 } from "lucide-react";
import { api, apiPath } from "@/lib/client";
import { t as translate, errorText } from "@/lib/locale";
import { useResource } from "@/lib/use-resource";
import { SecureImage } from "@/pages/live-shared";
import "./PhotoPicker.css";

const types = ["image/jpeg", "image/png", "image/webp"];
const maxBytes = 5 * 1024 * 1024; // backend image_max_bytes

function check(file) {
  if (!file) return "";
  if (!types.includes(file.type))
    return translate("Only JPEG, PNG or WebP images.");
  if (file.size > maxBytes) return translate("Each photo must be under 5 MB.");
  return "";
}

// The event poster (cover image). Two modes:
// - new event: `value`/`onChange` hold { file, url } until the draft exists;
// - saved event: `eventId` uploads/replaces/removes the cover right away.
export default function PosterPicker({ value, onChange, eventId }) {
  const live = Boolean(eventId);
  const images = useResource(live ? `/events/${eventId}/images` : null, true);
  // Only the image marked as cover is the poster; other photos stay photos.
  const cover = live ? images.data?.find((i) => i.is_cover) : null;
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const input = useRef(null);
  const latest = useRef(value);
  useEffect(() => {
    latest.current = value;
  }, [value]);
  useEffect(
    () => () => {
      if (latest.current?.url) URL.revokeObjectURL(latest.current.url);
    },
    [],
  );

  async function pick(file) {
    const problem = check(file);
    setError(problem);
    if (!file || problem) return;
    if (!live) {
      if (value?.url) URL.revokeObjectURL(value.url);
      onChange({ file, url: URL.createObjectURL(file) });
      return;
    }
    setBusy(true);
    try {
      const data = new FormData();
      data.append("file", file);
      data.append("is_cover", "true");
      data.append("alt_text", "");
      await api(`/events/${eventId}/images`, { method: "POST", body: data });
      // Replacing: the old poster goes away instead of piling up as a photo.
      if (cover)
        await api(`/events/${eventId}/images/${cover.id}`, {
          method: "DELETE",
        }).catch(() => {});
      images.reload();
    } catch (failure) {
      setError(errorText(failure));
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    setError("");
    if (!live) {
      if (value?.url) URL.revokeObjectURL(value.url);
      onChange(null);
      return;
    }
    if (!cover || !window.confirm(translate("Remove the poster?"))) return;
    setBusy(true);
    try {
      await api(`/events/${eventId}/images/${cover.id}`, { method: "DELETE" });
      images.reload();
    } catch (failure) {
      setError(errorText(failure));
    } finally {
      setBusy(false);
    }
  }

  const has = live ? Boolean(cover) : Boolean(value);
  return (
    <div className="bf-poster">
      <span className="bf-photos-label">{translate("Poster")}</span>
      <div
        className={`bf-poster-drop${drag ? " is-drag" : ""}${has ? " has-image" : ""}`}
        aria-busy={busy || undefined}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          pick(e.dataTransfer.files[0]);
        }}
      >
        {has ? (
          <>
            <div className="bf-poster-image">
              {live ? (
                <SecureImage path={apiPath(cover.url)} alt="" />
              ) : (
                <img src={value.url} alt="" />
              )}
            </div>
            <div className="bf-poster-actions">
              <button
                type="button"
                className="bf-outline-button"
                disabled={busy}
                onClick={() => input.current?.click()}
              >
                <RefreshCw aria-hidden="true" />
                {translate("Replace poster")}
              </button>
              <button
                type="button"
                className="bf-outline-button"
                disabled={busy}
                onClick={remove}
              >
                <Trash2 aria-hidden="true" />
                {translate("Remove")}
              </button>
            </div>
          </>
        ) : (
          <button
            type="button"
            className="bf-poster-empty"
            disabled={busy}
            onClick={() => input.current?.click()}
          >
            <ImageUp aria-hidden="true" />
            <b>
              {busy
                ? translate("Uploading…")
                : translate("Upload the event poster")}
            </b>
            <span>{translate("Click or drop a file here")}</span>
            <small>
              {translate(
                "JPEG, PNG or WebP up to 5 MB. Vertical 4:5 (1200×1500) looks best.",
              )}
            </small>
          </button>
        )}
      </div>
      {error && <p role="alert">{error}</p>}
      <input
        ref={input}
        type="file"
        accept={types.join(",")}
        hidden
        onChange={(e) => {
          pick(e.target.files[0]);
          e.target.value = "";
        }}
      />
    </div>
  );
}
