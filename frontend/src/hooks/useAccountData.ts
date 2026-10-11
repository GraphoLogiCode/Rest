import { useEffect, useRef, useState } from "react";
import { cloudEnabled, supabase } from "../services/cloudSession";
import { accountApi } from "../services/accountApi";
import {
  emptyData,
  readData,
  saveData,
  type RestData,
  type CheckIn,
} from "../services/storage";
const moods = ["", "Low", "Okay", "Good", "Great"];
const connections = ["", "Quiet time", "A little", "Connected"];
function fromCheckin(row: any): CheckIn {
  return {
    id: row.id,
    date: row.local_date,
    sleep: row.sleep_hours,
    mood: moods[row.mood || 0],
    social: connections[row.connection || 0],
    note: row.note || "",
  };
}
function payload(entry: CheckIn) {
  return {
    sleep_hours: entry.sleep,
    mood: moods.indexOf(entry.mood) || null,
    connection: connections.indexOf(entry.social) || null,
    note: entry.note || null,
  };
}
export function useAccountData() {
  const [data, setData] = useState<RestData>(() =>
    cloudEnabled ? emptyData : readData(),
  );
  const [user, setUser] = useState<string | null>(null);
  const [ready, setReady] = useState(!cloudEnabled);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const owner = useRef<string | null>(null),
    generation = useRef(0),
    writing = useRef(false),
    version = useRef(0);
  const live = useRef(data);
  live.current = data;
  async function load(id: string, epoch: number) {
    const [checkins, routine, consents] = await Promise.all([
      accountApi("/v1/checkins", {}, id),
      accountApi("/v1/routine", {}, id),
      accountApi("/v1/consents", {}, id),
    ]);
    if (epoch !== generation.current) return;
    version.current = routine.version;
    setData({
      checkIns: checkins.items.map(fromCheckin),
      routine: routine.items,
    });
    setConsent(
      consents.items.some((c: any) => c.consent_type === "service" && c.active),
    );
    setReady(true);
  }
  useEffect(() => {
    if (!supabase) return;
    const { data: subscription } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        const id = session?.user.id || null;
        if (id === owner.current) return;
        owner.current = id;
        const epoch = ++generation.current;
        setUser(id);
        setData(emptyData);
        setConsent(false);
        setReady(false);
        setError("");
        // Do not call Supabase auth methods from inside its auth-state callback.
        if (id)
          setTimeout(() => {
            if (epoch === generation.current)
              void load(id, epoch).catch((e) => {
                if (epoch === generation.current) setError(e.message);
              });
          }, 0);
      },
    );
    return () => {
      generation.current++;
      owner.current = null;
      subscription.subscription.unsubscribe();
    };
  }, []);
  async function run(action: (id: string, epoch: number) => Promise<void>) {
    if (writing.current || !owner.current) return false;
    const id = owner.current,
      epoch = generation.current;
    writing.current = true;
    setBusy(true);
    setError("");
    try {
      await action(id, epoch);
      return epoch === generation.current;
    } catch (e) {
      if (epoch === generation.current)
        setError(e instanceof Error ? e.message : "Request failed.");
      return false;
    } finally {
      writing.current = false;
      setBusy(false);
    }
  }
  async function update(next: RestData) {
    if (!cloudEnabled) {
      try {
        saveData(next);
        setData(next);
        return true;
      } catch {
        setError(
          "Browser storage is unavailable. Your changes were not saved.",
        );
        return false;
      }
    }
    if (!ready || !consent) {
      setError("Sign in and enable account saving first.");
      return false;
    }
    return run(async (id, epoch) => {
      const previous = live.current;
      let saved = previous;
      if (JSON.stringify(previous.routine) !== JSON.stringify(next.routine)) {
        const result = await accountApi(
          "/v1/routine",
          {
            method: "PUT",
            body: JSON.stringify({
              version: version.current,
              items: next.routine,
            }),
          },
          id,
        );
        if (epoch !== generation.current) return;
        version.current = result.version;
        saved = { ...saved, routine: result.items };
      }
      for (const entry of next.checkIns) {
        const existing = previous.checkIns.find((c) => c.date === entry.date);
        if (JSON.stringify(existing) === JSON.stringify(entry)) continue;
        const result = await accountApi(
          existing?.id ? `/v1/checkins/${existing.id}` : "/v1/checkins",
          {
            method: existing?.id ? "PATCH" : "POST",
            body: JSON.stringify(
              existing?.id
                ? payload(entry)
                : { local_date: entry.date, ...payload(entry) },
            ),
          },
          id,
        );
        if (epoch !== generation.current) return;
        saved = {
          ...saved,
          checkIns: [
            ...saved.checkIns.filter((c) => c.date !== entry.date),
            fromCheckin(result),
          ],
        };
      }
      if (epoch === generation.current) setData(saved);
    });
  }
  const reload = () =>
    run(async (id, epoch) => {
      await load(id, epoch);
    });
  const enable = () =>
    run(async (id, epoch) => {
      await accountApi(
        "/v1/consents/service",
        {
          method: "PUT",
          body: JSON.stringify({ version: "account-saving-2026-10-11" }),
        },
        id,
      );
      await accountApi(
        "/v1/me",
        {
          method: "PATCH",
          body: JSON.stringify({
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          }),
        },
        id,
      );
      await load(id, epoch);
    });
  const importLocal = () =>
    run(async (id, epoch) => {
      if (!consent) throw new Error("Enable account saving first.");
      const local = readData();
      // Existing account dates win. Repeated imports never overwrite a newer account entry.
      const existing = await accountApi("/v1/checkins", {}, id);
      const dates = new Set(existing.items.map((c: any) => c.local_date));
      for (const entry of local.checkIns) {
        if (epoch !== generation.current) return;
        if (!dates.has(entry.date))
          await accountApi(
            "/v1/checkins",
            {
              method: "POST",
              body: JSON.stringify({
                local_date: entry.date,
                ...payload(entry),
              }),
            },
            id,
          );
      }
      if (epoch !== generation.current) return;
      const routine = await accountApi("/v1/routine", {}, id);
      const ids = new Set(routine.items.map((s: any) => s.id));
      await accountApi(
        "/v1/routine",
        {
          method: "PUT",
          body: JSON.stringify({
            version: routine.version,
            items: [
              ...routine.items,
              ...local.routine.filter((s) => !ids.has(s.id)),
            ],
          }),
        },
        id,
      );
      await load(id, epoch);
    });
  const clearAccount = () =>
    run(async (id, epoch) => {
      await accountApi("/v1/account", { method: "DELETE" }, id);
      await load(id, epoch);
    });
  return {
    clearAccount,
    data,
    setData,
    user,
    ready,
    consent,
    busy,
    error,
    update,
    reload,
    enable,
    importLocal,
    cloud: cloudEnabled,
  };
}
