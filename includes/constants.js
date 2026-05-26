// OULAD Data Platform — Shared constants & helpers
// Accessible in SQLX as ${constants.xxx}

const PII_FIELDS = ["region", "imd_band"];

const VALID_FINAL_RESULTS = ["Pass", "Fail", "Withdrawn", "Distinction"];

const VALID_ASSESSMENT_TYPES = ["TMA", "CMA", "Exam"];

const ACTIVITY_CATEGORY_MAP = [
  { types: ["forumng", "glossary"], category: "communication" },
  { types: ["oucontent", "htmlactivity", "page", "subpage"], category: "content" },
  { types: ["quiz", "externalquiz", "questionnaire"], category: "assessment" },
  { types: ["resource", "url", "folder", "sharedsubpage"], category: "reference" },
  { types: ["homepage", "dataplus", "dualpane", "repeatactivity"], category: "tool" },
];

const WEEK_DURATION = 7;

module.exports = {
  PII_FIELDS,
  VALID_FINAL_RESULTS,
  VALID_ASSESSMENT_TYPES,
  ACTIVITY_CATEGORY_MAP,
  WEEK_DURATION,
};
