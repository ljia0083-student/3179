// Shared look for every chart, so the Vega-Lite specs only describe the data
// and encodings. Colours and fonts match css/styles.css.
const ink = "#1E2328";
const inkSoft = "#4A525A";
const chartFont = "Overpass, 'Helvetica Neue', Arial, sans-serif";

const theme = {
  background: "transparent",
  font: chartFont,
  view: { stroke: null },
  axis: {
    labelColor: inkSoft,
    labelFontSize: 12,
    titleColor: inkSoft,
    titleFontSize: 12,
    titleFontWeight: 600,
    gridColor: "#E4E6E3",
    domainColor: "#B9BDC1",
    tickColor: "#B9BDC1"
  },
  legend: {
    labelColor: inkSoft,
    labelFontSize: 12,
    titleColor: ink,
    titleFontSize: 12,
    titleFontWeight: 700
  },
  header: { labelColor: ink, labelFont: chartFont, titleFont: chartFont },
  text: { color: ink, font: chartFont }
};

const options = { actions: false, renderer: "svg", config: theme };

// [container id, Vega-Lite spec]
const charts = [
  ["#vis-unit", "js/unit_people_killed.vg.json"],
  ["#vis-annual", "js/line_annual_deaths.vg.json"],
  ["#vis-outcome", "js/marimekko_outcome.vg.json"],
  ["#vis-choro-state", "js/map_choropleth_state.vg.json"],
  ["#vis-choro-melb", "js/map_choropleth_melbourne.vg.json"],
  ["#vis-symbol-state", "js/map_symbol_state.vg.json"],
  ["#vis-symbol-melb", "js/map_symbol_melbourne.vg.json"],
  ["#vis-dots", "js/map_dot_fatal.vg.json"],
  ["#vis-speed", "js/bar_speed_fatal.vg.json"]
];

charts.forEach(([el, spec]) => {
  vegaEmbed(el, spec, options).catch((err) => {
    console.error(spec, err);
    document.querySelector(el).textContent = "This chart could not load. Refresh the page to try again.";
  });
});
