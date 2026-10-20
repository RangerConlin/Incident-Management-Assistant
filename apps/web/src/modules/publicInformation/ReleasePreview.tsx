import type { PioMessage, PioRecord } from "../../api/types";
import { mergePreview } from "./model";

export default function ReleasePreview({ message, template, incident }: { message: Partial<PioMessage>; template?: PioRecord; incident?: { name?: string; number?: string } }) {
  const render = (key: string) => mergePreview(String(template?.[key] ?? ""), message, template, incident);
  return <article><p>{String(template?.agency_name ?? "")}</p>{template?.header_text ? <pre>{render("header_text")}</pre> : null}
    <p><strong>{String(template?.release_label || message.type || "")}</strong></p><h1>{message.title || "Untitled release"}</h1>
    {message.subtitle && <h2>{message.subtitle}</h2>}<p><strong>{message.dateline}</strong></p><div>{message.body}</div>
    {message.next_update_statement && <p><strong>Next update:</strong> {message.next_update_statement}</p>}<p>{message.boilerplate}</p>
    {template?.contact_block ? <pre>{render("contact_block")}</pre> : null}{template?.footer_text ? <pre>{render("footer_text")}</pre> : null}<p>{String(template?.default_footer_disclaimer ?? "")}</p>
  </article>;
}
