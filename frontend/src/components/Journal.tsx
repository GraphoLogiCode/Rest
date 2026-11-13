import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type Dispatch,
  type SetStateAction,
} from "react";
import { ArrowRight, Camera, ImagePlus, X } from "lucide-react";
import { ProgressJournal } from "./ProgressJournal";
import { FaceEditor } from "./FaceEditor";
import { localDate } from "../services/storage";

export type Photo = { url: string; file: File; date: string };
export function Journal({
  photos,
  setPhotos,
  user,
  canSave,
}: {
  user: string | null;
  canSave: boolean;
  photos: (Photo | null)[];
  setPhotos: Dispatch<SetStateAction<(Photo | null)[]>>;
}) {
  const [tab, setTab] = useState(user ? "saved" : "photos");
  const [mode, setMode] = useState("side");
  const [slider, setSlider] = useState(50);
  const [error, setError] = useState("");
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  async function upload(event: ChangeEvent<HTMLInputElement>, index: number) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setError("");
    if (
      !["image/jpeg", "image/png", "image/webp"].includes(file.type) ||
      file.size > 10 * 1024 * 1024
    ) {
      setError("Choose a JPG, PNG, or WebP image under 10 MB.");
      return;
    }
    const url = URL.createObjectURL(file);
    try {
      const image = new Image();
      image.src = url;
      await image.decode();
      if (!active.current) {
        URL.revokeObjectURL(url);
        return;
      }
      setPhotos((previous) => {
        const next = [...previous];
        if (next[index]) URL.revokeObjectURL(next[index]!.url);
        next[index] = { url, file, date: localDate() };
        return next;
      });
    } catch {
      URL.revokeObjectURL(url);
      if (active.current)
        setError("This image couldn’t be opened. Please choose another.");
    }
  }
  function remove(index: number) {
    const next = [...photos];
    if (next[index]) URL.revokeObjectURL(next[index]!.url);
    next[index] = null;
    setPhotos(next);
  }
  return (
    <>
      <div className="page-intro">
        <span className="eyebrow">YOUR SKIN JOURNAL</span>
        <h1>A little perspective.</h1>
        <p>Make space to notice change, at your own pace.</p>
      </div>
      <div className="tab-bar">
        <button
          className={tab === "photos" ? "selected" : ""}
          onClick={() => setTab("photos")}
        >
          My photo comparison
        </button>
        <button
          className={tab === "saved" ? "selected" : ""}
          onClick={() => setTab("saved")}
        >
          Saved progress & feedback
        </button>
        <button
          className={tab === "ai" ? "selected" : ""}
          onClick={() => setTab("ai")}
        >
          AI preview
        </button>
      </div>
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      {tab === "photos" ? (
        <section className="panel journal-panel">
          <div className="section-heading">
            <div>
              <h2>Your own before & after</h2>
              <p>Real photos. Your story.</p>
            </div>
            <div className="segmented">
              <button
                onClick={() => setMode("side")}
                className={mode === "side" ? "active" : ""}
              >
                Side by side
              </button>
              <button
                onClick={() => setMode("slider")}
                className={mode === "slider" ? "active" : ""}
                disabled={!photos.every(Boolean)}
              >
                Slider
              </button>
            </div>
          </div>
          <p className="photo-tip">
            <Camera size={17} /> Similar lighting, angle, and expression make
            comparisons more useful.
          </p>
          {mode === "slider" && photos.every(Boolean) ? (
            <div className="slider-block">
              <div className="comparison-stage">
                <img src={photos[1]!.url} alt="Later photo" />
                <img
                  className="before-layer"
                  src={photos[0]!.url}
                  alt="Earlier photo"
                  style={{ clipPath: `inset(0 ${100 - slider}% 0 0)` }}
                />
                <div className="slider-divider" style={{ left: `${slider}%` }}>
                  <span>↔</span>
                </div>
                <span className="photo-label left">Before</span>
                <span className="photo-label right">After</span>
              </div>
              <label className="slider-control">
                Reveal before and after
                <input
                  aria-label="Photo comparison position"
                  type="range"
                  min="0"
                  max="100"
                  value={slider}
                  onChange={(e) => setSlider(Number(e.target.value))}
                />
              </label>
            </div>
          ) : (
            <div className="photo-grid">
              {[0, 1].map((index) => (
                <div key={index} className="photo-slot">
                  <div className="photo-slot-head">
                    <span>{index === 0 ? "01 / BEFORE" : "02 / AFTER"}</span>
                    {photos[index] && (
                      <button
                        className="icon-button"
                        aria-label={`Remove ${index === 0 ? "before" : "after"} photo`}
                        onClick={() => remove(index)}
                      >
                        <X size={18} />
                      </button>
                    )}
                  </div>
                  {photos[index] ? (
                    <img
                      className="journal-image"
                      src={photos[index]!.url}
                      alt={
                        index === 0 ? "Your earlier photo" : "Your later photo"
                      }
                    />
                  ) : (
                    <label className="photo-upload">
                      <span className="icon-orbit">
                        <ImagePlus size={27} />
                      </span>
                      <strong>
                        {index === 0
                          ? "Start with a moment"
                          : "See what changes"}
                      </strong>
                      <span>
                        Add your {index === 0 ? "first" : "follow-up"} photo
                      </span>
                      <span className="button secondary">
                        Choose a photo <ArrowRight size={16} />
                      </span>
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        aria-label={`Upload ${index === 0 ? "before" : "after"} photo`}
                        onChange={(e) => void upload(e, index)}
                      />
                    </label>
                  )}
                  {photos[index] && (
                    <label className="photo-date">
                      Photo date
                      <input
                        aria-label={`${index === 0 ? "Before" : "After"} photo date`}
                        type="date"
                        value={photos[index]!.date}
                        max={localDate()}
                        onChange={(e) => {
                          const next = [...photos];
                          next[index] = {
                            ...next[index]!,
                            date: e.target.value,
                          };
                          setPhotos(next);
                        }}
                      />
                    </label>
                  )}
                </div>
              ))}
            </div>
          )}
          <p className="small-text journal-foot">
            Photos stay in this tab and are cleared on refresh. Photo
            differences do not establish what caused a change.
          </p>
        </section>
      ) : tab === "ai" ? (
        <FaceEditor key={user || "local"} />
      ) : (
        <ProgressJournal key={user || "local"} user={user} canSave={canSave} />
      )}
    </>
  );
}
