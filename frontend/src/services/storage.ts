export type CheckIn = {
  id?: string;
  date: string;
  sleep: number | null;
  mood: string;
  social: string;
  note: string;
};
export type RoutineStep = {
  id: string;
  name: string;
  period: "morning" | "evening";
  completedOn?: string;
  product_id?: string;
};
export type RestData = { checkIns: CheckIn[]; routine: RoutineStep[] };
const KEY = "rest.local.v1";
export const emptyData: RestData = { checkIns: [], routine: [] };
// randomUUID requires HTTPS; getRandomValues also works on a phone's LAN URL.
export function createLocalId() {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}
export function localDate() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}
export function readData(): RestData {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) || "null");
    if (
      !value ||
      !Array.isArray(value.checkIns) ||
      !Array.isArray(value.routine)
    )
      return emptyData;
    return {
      checkIns: value.checkIns.filter(
        (x: CheckIn) =>
          x &&
          typeof x.date === "string" &&
          (x.sleep === null ||
            (Number.isFinite(x.sleep) && x.sleep >= 0 && x.sleep <= 24)) &&
          ["Low", "Okay", "Good", "Great"].includes(x.mood) &&
          ["Quiet time", "A little", "Connected"].includes(x.social) &&
          typeof x.note === "string",
      ),
      routine: value.routine.filter(
        (x: RoutineStep) =>
          x &&
          typeof x.id === "string" &&
          typeof x.name === "string" &&
          ["morning", "evening"].includes(x.period),
      ),
    };
  } catch {
    return emptyData;
  }
}
export function saveData(data: RestData) {
  localStorage.setItem(KEY, JSON.stringify(data));
}
export function deleteData() {
  localStorage.removeItem(KEY);
}
