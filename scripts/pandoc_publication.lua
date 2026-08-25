-- Publication-only Pandoc filter.
-- The software architecture Markdown keeps process-model blocks as source of truth,
-- but DOCX/PDF must show the generated diagrams rather than the machine-readable JSON.

function CodeBlock(el)
  if el.classes:includes('process-model') then
    return {}
  end
  return el
end

function RawBlock(el)
  if el.format == 'html' and el.text:match('GENERATED_MERMAID:') then
    return {}
  end
  return el
end
