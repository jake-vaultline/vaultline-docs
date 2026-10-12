# Portal import preview

No live writes occurred. Use the existing Portal administrator Documents form after approval.
Choose the client organization and a Resource document, attach the listed PDF, then save.
The Portal obtains a signed upload intent, uploads bytes, and saves the document only after
validating its organization, file size and content type. Never submit package.json as a Portal API payload.
PDFs embed screenshots; uploading individual Markdown attachments does not resolve sibling image paths.
HTML and ZIP are local previews/archives; the Portal does not accept them as attachments.

Review package.json for each attachment path, size, SHA-256 and deployment. Live tenant ids
and upload ids are intentionally absent; the authenticated Portal generates them.
