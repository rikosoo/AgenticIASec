import { chatgpt } from "./chatgpt";
import { claude } from "./claude";
import { localtest } from "./localtest";
import type { SiteModule } from "./types";

export const SITES: SiteModule[] = __DEV__ ? [chatgpt, claude, localtest] : [chatgpt, claude];

export function siteFor(hostname: string): SiteModule | undefined {
  return SITES.find((s) => s.matches(hostname));
}
