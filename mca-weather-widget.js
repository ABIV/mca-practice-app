(function () {
  const config = window.MCA_WEATHER_CONFIG || {
    calendarUrl:
      "http://ical-cdn.teamsnap.com/team_schedule/085d0f1e-1abe-42ca-999e-ef79981f7bba.ics",
    daysToShow: 14,
    containerId: "mca-weather-widget"
  };

  const container = document.getElementById(config.containerId);

  if (!container) {
    console.error(
      "MCA Weather Widget: Missing container #" + config.containerId
    );
    return;
  }

  container.innerHTML = `
    <div class="mca-widget">
      <h2>MCA Weather Monitor</h2>
      <div class="mca-loading">Loading schedule...</div>
    </div>
  `;

  injectStyles();

  fetchCalendar();

  async function fetchCalendar() {
    try {
      const response = await fetch(config.calendarUrl);

      if (!response.ok) {
        throw new Error("Calendar fetch failed");
      }

      const text = await response.text();

      const events = parseICS(text);

      renderEvents(events);

    } catch (err) {
      console.error(err);

      container.innerHTML = `
        <div class="mca-widget">
          <h2>MCA Weather Monitor</h2>
          <p class="mca-error">
            Unable to load schedule.
          </p>
        </div>
      `;
    }
  }


  function parseICS(data) {

    const events = [];

    const blocks = data.split("BEGIN:VEVENT");

    blocks.forEach(block => {

      if (!block.includes("END:VEVENT")) return;


      const getValue = (key) => {
        const line = block
          .split("\n")
          .find(x => x.startsWith(key));

        if (!line) return "";

        return line
          .split(":")
          .slice(1)
          .join(":")
          .trim();
      };


      events.push({
        title: getValue("SUMMARY"),
        location: getValue("LOCATION"),
        start: parseDate(getValue("DTSTART")),
        end: parseDate(getValue("DTEND"))
      });

    });


    return events
      .filter(e => e.start)
      .filter(e => e.start >= new Date())
      .sort((a,b)=>a.start-b.start)
      .slice(0, config.daysToShow);

  }


  function parseDate(value){

    if(!value) return null;


    const year = value.substring(0,4);
    const month = value.substring(4,6);
    const day = value.substring(6,8);

    const hour = value.substring(9,11) || "00";
    const minute = value.substring(11,13) || "00";


    return new Date(
      `${year}-${month}-${day}T${hour}:${minute}:00`
    );

  }


  function renderEvents(events){

    if(!events.length){

      container.innerHTML = `
        <div class="mca-widget">
          <h2>MCA Weather Monitor</h2>
          <p>No upcoming events.</p>
        </div>
      `;

      return;
    }


    let html = `
      <div class="mca-widget">
      <h2>MCA Weather Monitor</h2>
    `;


    events.forEach(event=>{

      html += `
      <div class="mca-event">

        <div class="mca-date">
          ${formatDate(event.start)}
        </div>

        <div class="mca-title">
          ${event.title || "Practice"}
        </div>

        <div class="mca-location">
          📍 ${event.location || "Location unknown"}
        </div>

        <div class="mca-risk pending">
          Weather Risk: Checking soon...
        </div>

      </div>
      `;

    });


    html += "</div>";

    container.innerHTML = html;

  }


  function formatDate(date){

    return date.toLocaleString([],{
      weekday:"short",
      month:"short",
      day:"numeric",
      hour:"numeric",
      minute:"2-digit"
    });

  }


  function injectStyles(){

    const style=document.createElement("style");

    style.textContent=`

    .mca-widget{
      font-family:Arial,sans-serif;
      max-width:600px;
      margin:auto;
    }

    .mca-event{
      border:1px solid #ddd;
      border-radius:10px;
      padding:15px;
      margin:15px 0;
      background:white;
    }

    .mca-date{
      font-weight:bold;
      font-size:18px;
    }

    .mca-title{
      margin-top:8px;
      font-size:16px;
    }

    .mca-location{
      margin-top:8px;
      color:#555;
    }

    .mca-risk{
      margin-top:12px;
      padding:8px;
      border-radius:6px;
      background:#eee;
    }

    .mca-error{
      color:red;
    }

    `;

    document.head.appendChild(style);

  }


})();