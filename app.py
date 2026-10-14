from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
import re

import pandas as pd
import plotly.express as px
import plotly.io as pio
from shiny import App, reactive, render, ui

basepath =    str(Path(__file__).resolve().parent) + "/"
DATA_DIR = Path(basepath+"data")
DEFAULT_COLORS = "#red3,blue3,green3,gray60"
DEFAULT_SHAPES = "15,16,17,2"
DEFAULT_PARTIES_SPEC = "#REP,DEM,Other"
NON_PARTY_COLUMNS = {"Year", "Date", "County", "Total", "Check"}
MONTH_CHOICES = {
    "1": "January", "2": "February", "3": "March", "4": "April",
    "5": "May", "6": "June", "7": "July", "8": "August",
    "9": "September", "10": "October", "11": "November", "12": "December",
}

R_TO_PLOTLY_COLORS = {
    "blue3": "#0000CD",
    "green3": "#00CD00",
    "gray60": "#999999",
    "grey60": "#999999",
    "red3": "#CD0000",
}

R_TO_PLOTLY_SYMBOLS = {
    0: "circle-open",
    1: "circle",
    2: "triangle-up-open",
    15: "square",
    16: "circle",
    17: "triangle-up",
}

state_names = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"
}

presidential_dates = ["2000-11-07", "2004-11-02", "2008-11-04", "2012-11-06", "2016-11-08", "2020-11-03", "2024-11-05"]
midterm_dates      = ["2002-11-05", "2006-11-07", "2010-11-02", "2014-11-04", "2018-11-06", "2022-11-08", "2026-11-03"]
presidential_dates = pd.to_datetime(presidential_dates)
midterm_dates      = pd.to_datetime(midterm_dates)

def state_files() -> dict[str, Path]:
    files: dict[str, Path] = {}
    if not DATA_DIR.exists():
        return files
    for path in DATA_DIR.iterdir():
        if not path.is_file():
            continue
        #match = re.fullmatch(r"([A-Za-z]{2})_reg\.csv", path.name)
        #match = re.fullmatch(r"([A-Za-z]{2})_reg[A-Za-z_]*\.csv", path.name)
        match = re.fullmatch(r"([A-Za-z]{2}[A-Za-z_]*)_reg\.csv", path.name)
        if match:
            #files[match.group(1).upper()] = path
            file_id = match.group(1).upper()
            if len(file_id) >= 5:
                file_id = file_id[:4] + file_id[4:].lower()
            file_idx = state_names[file_id[:2].upper()] + file_id[2:]
            files[file_idx] = path
    return dict(sorted(files.items()))


STATE_FILES = state_files()
STATE_CHOICES = list(STATE_FILES) or ["AZ"]
#FILE_PROPS_DF = pd.read_csv(str(DATA_DIR)+"/../file_props.csv")
FILE_PROPS_DF = pd.read_csv(basepath + "file_props.csv")

FILE_PROPS_COLUMNS = {"state", "active", "all", "parties", "precolors"}
if set(FILE_PROPS_DF.columns) != FILE_PROPS_COLUMNS:
    missing_columns = FILE_PROPS_COLUMNS - set(FILE_PROPS_DF.columns)
    unexpected_columns = set(FILE_PROPS_DF.columns) - FILE_PROPS_COLUMNS
    raise ValueError(
        "Invalid file_props.csv columns. "
        f"Missing: {sorted(missing_columns)}; "
        f"Unexpected: {sorted(unexpected_columns)}"
    )

duplicate_states = FILE_PROPS_DF.loc[
    FILE_PROPS_DF["state"].duplicated(keep=False), "state"
].unique()
if len(duplicate_states):
    raise ValueError(
        f"Duplicate states in file_props.csv: {', '.join(sorted(duplicate_states))}"
    )

for column in ("active", "all"):
    normalized = FILE_PROPS_DF[column].astype(str).str.strip().str.lower()
    invalid_rows = ~normalized.isin({"true", "false"})
    if invalid_rows.any():
        invalid_states = FILE_PROPS_DF.loc[invalid_rows, "state"].astype(str)
        raise ValueError(
            f"Invalid Boolean value in file_props.csv column '{column}' for: "
            f"{', '.join(invalid_states)}"
        )
    FILE_PROPS_DF[column] = normalized.eq("true")

missing_states = set(STATE_FILES) - set(FILE_PROPS_DF["state"])
if missing_states:
    raise ValueError(
        f"Missing states in file_props.csv: {', '.join(sorted(missing_states))}"
    )

FILE_PROPS = FILE_PROPS_DF.set_index("state").to_dict(orient="index")


def effective_voter_type(state: str, requested: str | None) -> str:
    props = FILE_PROPS[state]

    if requested == "active" and props["active"]:
        return "active"
    if requested == "all" and props["all"]:
        return "all"

    # The selected radio value can be briefly stale when the state changes.
    if props["active"]:
        return "active"
    if props["all"]:
        return "all"

    raise ValueError(f"No voter registration data configured for {state}")


@lru_cache(maxsize=None)
def read_state_data(state: str, voter_type: str | None) -> pd.DataFrame:
    path = STATE_FILES[state]
    voter_type = effective_voter_type(state, voter_type)
    props = FILE_PROPS[state]

    # For states with both data sets, the base file contains Active voters
    # and the companion *_all.csv file contains All voters. States with only
    # one data set continue to use the base file.
    if voter_type == "all" and props["active"] and props["all"]:
        path = path.with_name(path.stem + "_all.csv")

    df = pd.read_csv(path)
    df.columns = [str(col).strip() for col in df.columns]
    df = df.copy()
    rename_columns = {}
    if "YEAR" in df.columns:
        rename_columns["YEAR"] = "Year"
    if "COUNTY" in df.columns:
        rename_columns["COUNTY"] = "County"
    df = df.rename(columns=rename_columns)
    if "MO" in df.columns:
        df = df.drop(columns="MO")

    df["County"] = df["County"].astype(str).str.upper().str.strip()
    df["Date"] = pd.to_datetime(df["Date"])

    first_cols = ["Year", "Date", "County", "Total", "REP", "DEM"]
    existing_first_cols = [col for col in first_cols if col in df.columns]
    other_cols = [col for col in df.columns if col not in first_cols]
    df = df[existing_first_cols + other_cols]
    return df


def party_columns(df: pd.DataFrame) -> list[str]:
    return [column for column in df.columns if column not in NON_PARTY_COLUMNS]


def state_county_choices(state: str, voter_type: str | None) -> list[str]:
    counties = (
        read_state_data(state, voter_type)["County"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    return ["TOTALS", *[county for county in counties if county != "TOTALS"]] \
        if "TOTALS" in counties else counties


def state_party_choices(state: str, voter_type: str | None) -> list[str]:
    return sorted(
        party_columns(read_state_data(state, voter_type)), key=str.upper
    )


def apply_parties_spec(df: pd.DataFrame, spec: str) -> pd.DataFrame:
    spec = spec.strip()
    if not spec or spec.startswith("#"):
        return df.copy()

    names = [name.strip() for name in spec.split(",") if name.strip()]
    if not names:
        return df.copy()

    source_parties = party_columns(df)
    kept_parties = names[:-1]
    other_label = names[-1]
    missing = [party for party in kept_parties if party not in source_parties]
    if missing:
        #raise ValueError(f"Unknown party column(s): {', '.join(missing)}")
        return False #DEBUG_TMP_260916 ignore bad parties
    if len(kept_parties) != len(set(kept_parties)):
        raise ValueError("Party names before the final label must be unique")
    if other_label in kept_parties:
        raise ValueError("The final party label must differ from the kept party names")

    remaining_parties = [
        party for party in source_parties if party not in kept_parties
    ]
    result = df.drop(columns=source_parties).copy()
    for party in kept_parties:
        result[party] = df[party]
    if remaining_parties:
        result[other_label] = df[remaining_parties].sum(
            axis="columns", min_count=1
        )
    else:
        result[other_label] = 0
    return result


def configured_party_choices(
    state: str, voter_type: str | None, spec: str
) -> list[str]:
    if not spec.strip() or spec.strip().startswith("#"):
        return state_party_choices(state, voter_type)
    return party_columns(
        apply_parties_spec(read_state_data(state, voter_type), spec)
    )


def selected_state() -> str:
    return STATE_CHOICES[0]


def selected_party() -> str:
    #return state_party_choices(selected_state())[0]
    return "DEM"


def parse_colors(value: str, parties: list[str]) -> dict[str, str]:
    colors = [R_TO_PLOTLY_COLORS.get(x.strip(), x.strip()) for x in value.split(",")]
    while len(colors) < len(parties):
        colors.append(None)
    return dict(zip(parties, colors))


def parse_symbols(value: str, parties: list[str]) -> dict[str, str]:
    try:
        symbols = [R_TO_PLOTLY_SYMBOLS.get(int(x.strip()), "circle") for x in value.split(",")]
    except ValueError:
        symbols = ["circle"] * len(parties)
    while len(symbols) < len(parties):
        symbols.append("circle")
    return dict(zip(parties, symbols))


def selected_filename(input, suffix: str) -> str:
    change = "_change" if input.dochange() else ""
    if input.plotcounties():
        return f"reg_{input.xstate()}_counties_{input.xparty()}{change}.{suffix}"
    return f"reg_{input.xstate()}_{input.xcounty()}{change}.{suffix}"


def apply_year_step(fig, input) -> None:
    year_step = max(0, int(input.stepyear() or 0))
    if year_step == 0:
        return

    # Anchor the ticks to a year divisible by the requested step. This makes
    # a step of 2 display even years, a step of 3 display years divisible by
    # 3, and so on.
    tick_year = 2000 - (2000 % year_step)
    fig.update_xaxes(
        tickmode="linear",
        tick0=f"{tick_year}-01-01",
        dtick=f"M{12 * year_step}",
        tickformat="%Y",
    )


def make_plot(df: pd.DataFrame, input, *, interactive: bool = True):
    start_period = f"{MONTH_CHOICES[str(input.minmonth())]} {input.minyear()}"
    prefix1 = f"Change since {start_period} in " if input.dochange() else ""
    percent = input.plotpercent()
    lcount = "Thousands of " if input.dothousands() else "Number of "
    parties = party_columns(df)
    voter_type = effective_voter_type(input.xstate(), input.votertype())
    regtype = "Active " if voter_type == "active" else ""

    if input.plotcounties():
        party = input.xparty()
        plot_df = df[["County", "Date", party]].rename(columns={party: "Registered"}).copy()
        if input.dothousands() and not percent:
            plot_df["Registered"] = plot_df["Registered"] / 1000

        if percent:
            if input.dochange():
                title_metric = f"Percent Change since {start_period} in {party} {regtype}Registered Voters"
                y_title = f"Percent Change in {party} {regtype}Registered Voters"
            else:
                title_metric = f"{party} {regtype}Registered Voter Percent"
                y_title = f"Percent of Total {regtype}Registered Voters that are {party}"
        else:
            title_metric = f"{prefix1}{lcount}{party} {regtype}Registered Voters"
            y_title = f"{'Change in ' if input.dochange() else ''}{lcount}{party} {regtype}Registered Voters"

        county_colors = (
            px.colors.qualitative.Dark24
            + px.colors.qualitative.Light24
            + px.colors.qualitative.Set3
            + px.colors.qualitative.Alphabet
        )
        title = f"{input.xstate()} Counties - {title_metric}"
        plot_df = plot_df.sort_values('Date') # DEBUG_260615 sort by Date 
        fig = px.line(
            plot_df,
            x="Date",
            y="Registered",
            color="County",
            line_dash="County",
            color_discrete_sequence=county_colors,
            title=title,
            height = input.height()
        )
        fig.update_traces(connectgaps=True, line={"width": 1.7}, opacity=0.85)
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title=y_title,
            legend_title_text="County",
            margin={"l": 60, "r": 20, "t": 70, "b": 60},
            template="plotly_white",
        )
        apply_year_step(fig, input)
        xmin = df["Date"].min()
        xmax = df["Date"].max()
        if input.mark_generals():
            for d in presidential_dates:
                if xmin <= d <= xmax:
                    fig.add_vline(
                        x=d,
                        line_color="#6A3D9A", # deep purple
                        line_width=1
                    )
        if input.mark_midterms():
            for d in midterm_dates:
                if xmin <= d <= xmax:
                    fig.add_vline(
                        x=d,
                        line_color="brown",
                        line_width=1,
                        line_dash="dash"
                    )
        if not interactive:
            fig.update_layout(dragmode=False, showlegend=False)
        return fig

    plot_df = df.melt(
        id_vars=["County", "Total", "Year", "Date"],
        value_vars=parties,
        var_name="Party",
        value_name="Registered",
    )
    if input.dothousands() and not percent:
        plot_df["Registered"] = plot_df["Registered"] / 1000

    if percent:
        if input.dochange():
            title_metric = f"Percent Change since {start_period} in {regtype}Registered Voters by Party"
            y_title = "Percent Change in {regtype}Registered Voters"
        else:
            title_metric = "{regtype}Registered Voter Percent by Party"
            y_title = "Percent of Total {regtype}Registered Voters"
    else:
        title_metric = f"{prefix1}{lcount}{regtype}Registered Voters by Party"
        y_title = f"{'Change in ' if input.dochange() else ''}{lcount}{regtype}Registered Voters"

    title = f"{input.xcounty()}, {input.xstate()} - {title_metric}"

    input_xcolor = input.xcolor()
    if input_xcolor.startswith("#"):
        if input.plotgroup() == "min":
            input_xcolor = "Black"
        else:
            input_xcolor = FILE_PROPS[input.xstate()]["precolors"]

    fig = px.line(
        plot_df,
        x="Date",
        y="Registered",
        color="Party",
        symbol="Party",
        markers=True,
        color_discrete_map=parse_colors(input_xcolor, parties),
        symbol_map=parse_symbols(input.xshape(), parties),
        title=title,
        height = input.height()
    )
    fig.update_traces(connectgaps=True, marker={"size": input.dotsize(), "opacity": 0.7}, line={"width": 2})
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title=y_title,
        legend_title_text="Party",
        margin={"l": 60, "r": 20, "t": 70, "b": 60},
        template="plotly_white",
    )
    apply_year_step(fig, input)
    xmin = df["Date"].min()
    xmax = df["Date"].max()
    if input.mark_generals():
        for d in presidential_dates:
            if xmin <= d <= xmax:
                fig.add_vline(
                    x=d,
                    line_color="#6A3D9A", # deep purple
                    line_width=1
                )
    if input.mark_midterms():
        for d in midterm_dates:
            if xmin <= d <= xmax:
                fig.add_vline(
                    x=d,
                    line_color="brown",
                    line_width=1,
                    line_dash="dash"
                )
    if not interactive:
        fig.update_layout(dragmode=False)
    return fig


app_ui = ui.page_fluid(
    ui.tags.style(
        """
        .app-header {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 16px;
        }
        .app-header h2 {
            margin: 0;
        }
        .app-logo {
            display: block;
            width: auto;
            height: 64px;
            object-fit: contain;
        }
        .app-shell {
            display: grid;
            grid-template-columns: 250px minmax(0, 1fr);
            gap: 24px;
            align-items: start;
        }

        .side-panel {
            background: #f5f5f5;
            border: 1px solid #e3e3e3;
            border-radius: 4px;
            padding: 15px;
        }

        .side-panel .form-group,
        .side-panel .shiny-input-container {
            width: 100%;
        }

        .side-panel .shiny-download-link {
            display: block;
            margin-bottom: 8px;
            width: 100%;
        }

        .county-nav {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin: -8px 0 12px;
        }

        .county-nav .btn {
            width: 100%;
        }

        .main-panel {
            min-width: 0;
        }

        @media (max-width: 768px) {
            .app-shell {
                grid-template-columns: 1fr;
            }
        }
        """
    ),
    ui.div(
        ui.a(
            ui.img(
                src="ETA_VOTE.png",
                alt="Election Truth Alliance",
                class_="app-logo",
            ),
            href="https://electiontruthalliance.org/",
            target="_blank",
            rel="noopener noreferrer",
        ),
        ui.h2("Voter Registration Trends Over Time"),
        class_="app-header",
    ),
    ui.div(
        ui.div(
            ui.input_select("xstate", "State", choices=STATE_CHOICES, selected=selected_state()),
            ui.layout_columns(
                ui.input_numeric("minyear", "Min Year", min=2017, max=2026, value=2017),
                ui.input_select(
                    "minmonth", "Min Month", choices=MONTH_CHOICES, selected="1"
                ),
            ),
            ui.layout_columns(
                ui.input_numeric("maxyear", "Max Year", min=2017, max=2026, value=2026),
                ui.input_numeric("stepyear", "Step Year", min=0, step=1, value=0),
            ),
            ui.input_select("xcounty", "County", choices=["TOTALS"], selected="TOTALS"),
            ui.div(
                ui.input_action_button("county_up", "▲", title="Previous county"),
                ui.input_action_button("county_down", "▼", title="Next county"),
                class_="county-nav",
            ),
            ui.input_select(
                "xparty",
                "Party",
                choices=state_party_choices(selected_state(), "active"),
                selected=selected_party(),
            ),
            ui.input_radio_buttons(
                 "votertype",
                 "Voter Type",
                 {
                     "active": "Active",
                     "all": "All"
                 },
                 selected="active",
                 inline=True
             ),
            ui.input_radio_buttons(
                "plotgroup",
                "Groups",
                {
                    "min": "Min",
                    "mid": "Mid",
                    "max": "Max"
                },
                selected="mid",
                inline=True
            ),
            ui.input_checkbox("dochange", "Calculate change", value=False),
            ui.input_checkbox("plotcounties", "Plot counties", value=False),
            #ui.input_checkbox("plotdetail", "Plot detail", value=False),
            ui.input_checkbox("plotpercent", "Plot percent", value=False),
            ui.input_checkbox("domonthly", "Plot monthly", value=True),
            ui.input_checkbox("dothousands", "Plot 1000s", value=False),
            ui.input_checkbox("mark_generals", "Mark generals", value=True),
            ui.input_checkbox("mark_midterms", "Mark midterms", value=True),
            ui.input_checkbox("addcheck", "Add check", value=False),
            ui.input_numeric("maxcounties", "Max counties", min=1, value=10),
            ui.input_text(
                "parties", "Parties", value=DEFAULT_PARTIES_SPEC
            ),
            ui.input_numeric("height", "Height", value=600),
            ui.input_numeric("dotsize", "Dot Size", value=8),
            ui.input_text("xcolor", "Color", value=DEFAULT_COLORS),
            ui.input_text("xshape", "Shape", value=DEFAULT_SHAPES),
            ui.download_button("getcsv", "Get CSV"),
            ui.download_button("getexcel", "Get Excel"),
            class_="side-panel",
        ),
        ui.div(
            ui.navset_tab(
                ui.nav_panel("Plotly", ui.output_ui("myPlotly")),
                #ui.nav_panel("Plot", ui.output_ui("myPlot")),
                ui.nav_panel("Data", ui.output_text_verbatim("myData")),
                ui.nav_panel(
                    "Usage",
                    ui.tags.iframe(
                        src="VoterRegistrationTrends.html",
                        style="width:100%; height:calc(100vh - 150px); border:none;"
                        # width="100%",
                        # height="800px",
                        # style="border: none;"
                    )
                ),
                selected="Plotly",
            ),
            class_="main-panel",
        ),
        class_="app-shell",
    ),
    ui.tags.script("""
    fetch("https://ipapi.co/json/")
    .then(response => response.json())
    .then(data => {
        Shiny.setInputValue("visitor_info", {
            ip: data.ip,
            city: data.city,
            region: data.region,
            country: data.country_name,
            latitude: data.latitude,
            longitude: data.longitude
        });
    });
    """)
)


def server(input, output, session):
    @reactive.effect
    def _populate_state_inputs():
        state = input.xstate()
        voter_type = input.votertype()
        state_df = read_state_data(state, voter_type)
        counties = state_county_choices(state, voter_type)
        minyear = int(state_df["Year"].min())
        maxyear = int(state_df["Year"].max())
        ui.update_numeric("minyear", min=minyear, max=maxyear, value=minyear, session=session)
        ui.update_numeric("maxyear", min=minyear, max=maxyear, value=maxyear, session=session)
        span = maxyear - minyear
        if span > 15 and span <= 32:
            ui.update_numeric("stepyear", min=0, step=1, value=2, session=session)
        elif span > 32:
            ui.update_numeric("stepyear", min=0, step=1, value=4, session=session)
        ui.update_select(
            "xcounty",
            choices=counties,
            selected="TOTALS" if "TOTALS" in counties else counties[0],
            session=session,
        )

    @reactive.effect
    def _populate_party_input():
        parties = configured_party_choices(
            input.xstate(), input.votertype(), input.parties()
        )
        current = input.xparty()
        selected = current if current in parties else parties[0]
        ui.update_select("xparty", choices=parties, selected=selected, session=session)

    def move_county(step: int) -> None:
        counties = state_county_choices(input.xstate(), input.votertype())
        if not counties:
            return
        current = input.xcounty()
        index = counties.index(current) if current in counties else 0
        ui.update_select("xcounty", selected=counties[(index + step) % len(counties)], session=session)

    @reactive.effect
    @reactive.event(input.xstate)
    def xstate_changed():
        state = input.xstate()
        # Code to run whenever xstate changes
        got_active = FILE_PROPS[input.xstate()]["active"]
        got_all    = FILE_PROPS[input.xstate()]["all"]
        if got_active and not got_all:
            ui.update_radio_buttons(
                "votertype",
                #  "Voter Type",
                #  {
                #      "active": "Active"
                #  },
                choices=["active"],
                selected="active"
                #inline=True
            )
        elif not got_active and got_all:
            ui.update_radio_buttons(
                "votertype",
                #  "Voter Type",
                #  {
                #      "active": "Active"
                #  },
                choices=["all"],
                selected="all"
                #inline=True
            )
        else:
            ui.update_radio_buttons(
                "votertype",
                # "Voter Type",
                # {
                #     "active": "Active",
                #     "all": "All"
                # },
                choices=["active","all"],
                selected="active"
                #inline=True
            )
        print(f"xstate changed to {state}")

    @reactive.effect
    @reactive.event(input.county_up)
    def _county_up():
        move_county(-1)

    @reactive.effect
    @reactive.event(input.county_down)
    def _county_down():
        move_county(1)

    @reactive.effect
    def _():
        info = input.visitor_info()

        if info:
            print("---> IP:", info.get("ip"))
            print(f"---> City: {info.get('city')}, {info.get('region')}, {info.get('country')}")
            print("---> Lat/Lon:", info.get("latitude"), info.get("longitude"))

    @reactive.calc
    def get_data() -> pd.DataFrame:
        minyear = int(input.minyear())
        minmonth = int(input.minmonth())
        maxyear = int(input.maxyear())
        if minyear > maxyear:
            minyear, maxyear = maxyear, minyear
        start_date = pd.Timestamp(year=minyear, month=minmonth, day=1)
        end_date = pd.Timestamp(year=maxyear + 1, month=1, day=1)

        # input_parties = input.parties()
        # if not input.plotdetail():
        #     input_parties = FILE_PROPS[input.xstate()]["parties"]
        input_parties = input.parties() # input.plotgroup() == "max"
        if input.plotgroup() == "mid":
            input_parties = FILE_PROPS[input.xstate()]["parties"]
        elif input.plotgroup() == "min":
            input_parties = "All"
        source_df = apply_parties_spec(
            read_state_data(input.xstate(), input.votertype()), input_parties
        )

        parties = party_columns(source_df)
        if input.addcheck():
            source_df = source_df.copy()
            source_df["Check"] = source_df["Total"] - source_df[parties].sum(
                axis="columns", min_count=1
            )
        df = source_df[
            (source_df["Date"] >= start_date) & (source_df["Date"] < end_date)
        ].copy()
        if input.plotcounties():
            df = df[df["County"] != "TOTALS"].copy()
        else:
            df = df[df["County"] == input.xcounty()].copy()

        if df.empty:
            return df

        if input.plotcounties() and not df.empty:
            max_counties = max(1, int(input.maxcounties()))
            latest_date = df["Date"].max()
            top_counties = (
                df[df["Date"] == latest_date]
                .sort_values("Total", ascending=False)
                .head(max_counties)["County"]
            )
            df = df[df["County"].isin(top_counties)].copy()

        if input.plotpercent() and not input.dochange() and not df.empty:
            df[parties] = df[parties].astype(float)
            df[parties] = df[parties].div(df["Total"], axis="index") * 100

        if input.dochange() and not df.empty:
            df[parties] = df[parties].astype(float)
            if input.plotcounties():
                first_values = df.groupby("County")[parties].transform("first")
            else:
                first_values = df.loc[df.index[0], parties]
            if input.plotpercent():
                df[parties] = (df[parties].div(first_values, axis="columns") - 1) * 100
            else:
                df[parties] = df[parties].subtract(first_values, axis="columns")

        if input.domonthly() and not input.plotcounties():
            #df = df.sort_values("Date").groupby(df["Date"].dt.to_period("M")).tail(1) # include last day of month
            df = df.sort_values("Date")
            idx = df.groupby(df["Date"].dt.to_period("M")).head(1).index # include first day of month
            idx = idx.union(df.tail(1).index) # plus last day if not already included
            df = df.loc[idx].sort_values("Date")

        return df

    @output
    @render.ui
    def myPlotly():
        fig = make_plot(get_data(), input, interactive=True)
        return ui.HTML(
            pio.to_html(fig, full_html=False, include_plotlyjs=True, config={"responsive": True})
        )

    @output
    @render.ui
    def myPlot():
        fig = make_plot(get_data(), input, interactive=False)
        return ui.HTML(
            pio.to_html(
                fig,
                full_html=False,
                include_plotlyjs=True,
                config={"displayModeBar": False, "staticPlot": True, "responsive": True},
            )
        )

    @output
    @render.text
    def myData():
        dd = get_data()
        dd.to_csv("mydata.csv", index=False)
        return get_data().to_string(index=False)

    @output
    @render.download(
        filename=lambda: selected_filename(input, "csv"),
        media_type="text/csv",
    )
    def getcsv():
        yield get_data().to_csv(index=False)

    @output
    @render.download(
        filename=lambda: selected_filename(input, "xlsx"),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    def getexcel():
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            get_data().to_excel(writer, index=False, sheet_name="Registration")
        yield buffer.getvalue()


app = App(app_ui, server, static_assets=Path(basepath + "www"))
