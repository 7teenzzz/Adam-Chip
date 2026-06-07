-- svg2png.lua -- Pandoc Lua filter: rewrite .svg image paths to .png
-- Applied automatically by build.ps1 via --lua-filter svg2png.lua

function Image(el)
  if el.src:match("%.svg$") then
    el.src = el.src:gsub("%.svg$", ".png")
  end
  return el
end
