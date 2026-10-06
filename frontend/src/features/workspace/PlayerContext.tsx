import { createContext, useContext } from "react";

/**
 * Lets any component inside the workspace (notes, flashcards, quiz, chat)
 * jump the video to a timestamp without passing callbacks through every level.
 */
export interface PlayerControls {
  canSeek: boolean;
  seekTo: (seconds: number) => void;
}

export const PlayerContext = createContext<PlayerControls>({ canSeek: false, seekTo: () => {} });

export function usePlayer(): PlayerControls {
  return useContext(PlayerContext);
}
