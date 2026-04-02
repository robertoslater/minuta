"use client";

import { create } from "zustand";
import type { Meeting, TranscriptSegment } from "@/lib/api";

interface AppState {
  // Recording state
  isRecording: boolean;
  currentMeetingId: string | null;
  setRecording: (recording: boolean, meetingId?: string | null) => void;

  // Live transcript
  liveSegments: TranscriptSegment[];
  addSegment: (segment: TranscriptSegment) => void;
  clearSegments: () => void;

  // Audio levels
  micLevel: number;
  systemLevel: number;
  setAudioLevels: (mic: number, system: number) => void;

  // Backend status
  backendConnected: boolean;
  setBackendConnected: (connected: boolean) => void;

  // License
  isPro: boolean;
  plan: string;
  setLicense: (isPro: boolean, plan: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  isRecording: false,
  currentMeetingId: null,
  setRecording: (recording, meetingId) =>
    set({ isRecording: recording, currentMeetingId: meetingId ?? null }),

  liveSegments: [],
  addSegment: (segment) =>
    set((state) => ({ liveSegments: [...state.liveSegments, segment] })),
  clearSegments: () => set({ liveSegments: [] }),

  micLevel: -60,
  systemLevel: -60,
  setAudioLevels: (mic, system) => set({ micLevel: mic, systemLevel: system }),

  backendConnected: false,
  setBackendConnected: (connected) => set({ backendConnected: connected }),

  isPro: false,
  plan: "Free",
  setLicense: (isPro, plan) => set({ isPro, plan }),
}));
