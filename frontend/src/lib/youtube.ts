/** Quick client-side check so we can warn about obviously wrong links before calling the API. */
const YOUTUBE_PATTERN =
  /^(https?:\/\/)?((www|m|music)\.)?(youtube\.com\/(watch\?|shorts\/|embed\/|live\/)|youtu\.be\/)[\w-]{11}/i;
const BARE_ID_PATTERN = /^[\w-]{11}$/;

export function looksLikeYouTubeUrl(text: string): boolean {
  const value = text.trim();
  return YOUTUBE_PATTERN.test(value) || BARE_ID_PATTERN.test(value);
}

export const ACCEPTED_FILE_TYPES = ".mp3,.mp4,.wav,.m4a,.webm,.ogg,.flac,.mkv,.mov,.aac,.opus";

export function isAcceptedFile(file: File): boolean {
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  return ACCEPTED_FILE_TYPES.split(",").includes(extension);
}
