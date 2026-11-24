import { useEffect, useRef, useState } from "react";
import { ImagePlus, Star, X } from "lucide-react";
import { t as translate } from "@/lib/locale";
import "./PhotoPicker.css";

const types = ["image/jpeg", "image/png", "image/webp"];
const maxBytes = 5 * 1024 * 1024; // backend image_max_bytes
const maxPhotos = 10;

// Photos chosen while the event does not exist yet; the parent uploads them
// once the draft is created. `photos` items: { id, file, url }; first = cover.
export default function PhotoPicker({ photos, onChange }) {
  const input = useRef(null);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState("");
  const latest = useRef(photos);
  useEffect(() => {
    latest.current = photos;
  }, [photos]);
  // Free preview URLs when the picker goes away.
  useEffect(
    () => () => latest.current.forEach((p) => URL.revokeObjectURL(p.url)),
    [],
  );

  function add(list) {
    const files = [...list];
    const bad = files.filter((f) => !types.includes(f.type));
    const big = files.filter(
      (f) => types.includes(f.type) && f.size > maxBytes,
    );
    const ok = files
      .filter((f) => types.includes(f.type) && f.size <= maxBytes)
      .slice(0, maxPhotos - photos.length);
    setError(
      bad.length
        ? translate("Only JPEG, PNG or WebP images.")
        : big.length
          ? translate("Each photo must be under 5 MB.")
          : files.length > ok.length
            ? translate("Up to 10 photos.")
            : "",
    );
    if (ok.length)
      onChange([
        ...photos,
        ...ok.map((file) => ({
          id: `${file.name}-${file.lastModified}-${Math.random()}`,
          file,
          url: URL.createObjectURL(file),
        })),
      ]);
  }
  function remove(id) {
    const gone = photos.find((p) => p.id === id);
    if (gone) URL.revokeObjectURL(gone.url);
    onChange(photos.filter((p) => p.id !== id));
  }
  function makeCover(id) {
    const pick = photos.find((p) => p.id === id);
    onChange([pick, ...photos.filter((p) => p.id !== id)]);
  }

  return (
    <div className="bf-photos">
      <span className="bf-photos-label">{translate("Photos")}</span>
      <div
        className={`bf-photos-drop${drag ? " is-drag" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          add(e.dataTransfer.files);
        }}
      >
        {photos.map((photo, index) => (
          <figure key={photo.id} className="bf-photo">
            <img src={photo.url} alt="" />
            {index === 0 ? (
              <span className="bf-photo-cover">{translate("Cover")}</span>
            ) : (
              <button
                type="button"
                className="bf-photo-btn bf-photo-star"
                aria-label={translate("Use as cover")}
                title={translate("Use as cover")}
                onClick={() => makeCover(photo.id)}
              >
                <Star aria-hidden="true" />
              </button>
            )}
            <button
              type="button"
              className="bf-photo-btn bf-photo-remove"
              aria-label={translate("Remove photo")}
              title={translate("Remove photo")}
              onClick={() => remove(photo.id)}
            >
              <X aria-hidden="true" />
            </button>
          </figure>
        ))}
        {photos.length < maxPhotos && (
          <button
            type="button"
            className="bf-photos-add"
            onClick={() => input.current?.click()}
          >
            <ImagePlus aria-hidden="true" />
            <span>
              {photos.length
                ? translate("Add more")
                : translate("Add photos or drop them here")}
            </span>
            <small>{translate("JPEG, PNG or WebP, up to 5 MB")}</small>
          </button>
        )}
      </div>
      {error && <p role="alert">{error}</p>}
      <input
        ref={input}
        type="file"
        accept={types.join(",")}
        multiple
        hidden
        onChange={(e) => {
          add(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
