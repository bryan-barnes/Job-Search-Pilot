// Job tracker data. One job per block, like this (see AGENTS.md for the fields and rules):
//
//   {
//     id: "company-role",
//     company: "Example",
//     role: "Director of Digital",
//     status: "new",
//     remote: "yes",
//     notes: "Where it came from and what's true about it.",
//     added: "2026-11-10",
//   },
//
// The board's buttons (tracker.html via board-server.py) edit this file. The ingest script adds
// new LinkedIn alert jobs. Keep it valid JavaScript.
window.JOBS = [
];
window.JOBS_UPDATED = "2026-11-10";
