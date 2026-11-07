/** Remember the last course name so the next class continues the series. */

const COURSE_KEY = "bb-course-pref";

export type CoursePref = {
  course_id: string;
  course_title: string;
};

export function readCoursePref(): CoursePref {
  try {
    const raw = sessionStorage.getItem(COURSE_KEY) || localStorage.getItem(COURSE_KEY);
    if (!raw) {
      return { course_id: "", course_title: "" };
    }
    const parsed = JSON.parse(raw) as CoursePref;
    return {
      course_id: String(parsed.course_id || "").slice(0, 64),
      course_title: String(parsed.course_title || "").slice(0, 120),
    };
  } catch {
    return { course_id: "", course_title: "" };
  }
}

export function storeCoursePref(courseId: string, courseTitle: string): void {
  const payload: CoursePref = {
    course_id: courseId.trim().slice(0, 64),
    course_title: courseTitle.trim().slice(0, 120),
  };
  const raw = JSON.stringify(payload);
  try {
    sessionStorage.setItem(COURSE_KEY, raw);
  } catch {
    // Ignore.
  }
  try {
    localStorage.setItem(COURSE_KEY, raw);
  } catch {
    // Ignore.
  }
}

export function courseIdFromTitle(title: string): string {
  return title
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "")
    .slice(0, 64);
}
