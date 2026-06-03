import { Capacitor, registerPlugin } from "@capacitor/core";

interface FactorySpeechPlugin {
  isAvailable(): Promise<{ recognition: boolean; speech: boolean }>;
  recognize(options: { lang: string }): Promise<{ transcript: string }>;
  speak(options: { text: string; lang: string }): Promise<void>;
  stop(): Promise<void>;
}

const FactorySpeech = registerPlugin<FactorySpeechPlugin>("FactorySpeech");

export async function canUseNativeSpeech(): Promise<boolean> {
  if (!Capacitor.isNativePlatform() || !Capacitor.isPluginAvailable("FactorySpeech")) {
    return false;
  }
  try {
    const result = await FactorySpeech.isAvailable();
    return Boolean(result.recognition);
  } catch {
    return false;
  }
}

export async function recognizeWithNativeSpeech(lang: string): Promise<string> {
  const result = await FactorySpeech.recognize({ lang });
  return result.transcript ?? "";
}

export async function speakWithNativeSpeech(text: string, lang: string): Promise<void> {
  await FactorySpeech.speak({ text, lang });
}

export async function stopNativeSpeech(): Promise<void> {
  if (!Capacitor.isNativePlatform() || !Capacitor.isPluginAvailable("FactorySpeech")) {
    return;
  }
  try {
    await FactorySpeech.stop();
  } catch {
    /* ignore cleanup failures */
  }
}
