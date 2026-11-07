// A template as a user's own CV would produce one: Geist, a teal rule under the header.
// It is the fake model's answer in the api tests (apps/api/src/api/ports/llm/fake.py keeps a
// copy) and a renderer test checks that it compiles through the sandbox as a `files` template.
#import "/_lib/cv.typ": *
#let cv = json("data.json")

#let teal = rgb("#0f766e")
#let muted = rgb("#5f6670")

#set document(title: cv.basics.name + " CV", author: cv.basics.name)
#set page(paper: paper-size(), margin: (x: 1.8cm, y: 1.5cm))
#set text(font: "Geist", size: 9.5pt, lang: "en", hyphenate: false)
#set par(leading: 0.55em, spacing: 0.7em)
#set list(marker: text(fill: teal)[•], indent: 0.1em, body-indent: 0.5em, spacing: 0.45em)

#let meta(body) = text(fill: muted, body)

#let section-heading(title) = block(above: 1.1em, below: 0.6em, sticky: true)[
  #text(size: 10pt, weight: "semibold", fill: teal, upper(title))
  #v(-0.55em)
  #line(length: 100%, stroke: 0.6pt + teal)
]

#let engagement(item) = pad(left: 0.8em, top: 0.1em)[
  #split-row(
    text(weight: "medium", item.name),
    meta(join-items((item.location, fmt-range(item.dates)), [ · ])),
  )
  #bullets(item.bullets)
]

#let experience(item) = block(below: 0.9em)[
  #split-row([*#item.role*, #item.org], meta(fmt-range(item.dates)))
  #if item.location.trim() != "" or item.stack.len() > 0 {
    v(-0.4em)
    meta(join-items((item.location, item.stack.join(", ")), [ · ]))
  }
  #bullets(item.bullets)
  #for engagement-item in item.engagements { src(engagement-item, engagement(engagement-item)) }
]

#let project(item) = block(below: 0.8em)[
  #split-row([*#item.name*], meta(item.year))
  #bullets(item.bullets)
]

#let education(item) = block(below: 0.7em)[
  #split-row([*#item.degree*, #item.institution], meta(fmt-range(item.dates)))
]

#let skills(groups) = grid(
  columns: (auto, 1fr),
  column-gutter: 0.9em,
  row-gutter: 0.55em,
  ..groups
    .map(group => (src(group, [*#group.label*]), src(group, group.items.join(", "))))
    .flatten(),
)

#let certification(item) = block(below: 0.5em)[
  #split-row([*#item.name*, #item.issuer], meta(fmt-date(item.date)))
]

#src("basics", [
  #text(size: 21pt, weight: "semibold", fill: teal, cv.basics.name)
  #if cv.basics.headline.trim() != "" {
    v(-0.5em)
    text(size: 11pt, cv.basics.headline)
  }
  #v(-0.3em)
  #meta(join-items(contact-items(cv.basics), [#h(0.4em)·#h(0.4em)]))
])

#if cv.summary.len() > 0 {
  src("summary", block(above: 0.9em, rich(cv.summary)))
}

#sections(
  cv,
  section-heading: section-heading,
  experience: experience,
  project: project,
  education: education,
  skills: skills,
  certification: certification,
)
