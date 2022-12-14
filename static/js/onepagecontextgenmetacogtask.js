function csrfSafeMethod(method) {
  // these HTTP methods do not require CSRF protection
  return /^(GET|HEAD|OPTIONS|TRACE)$/.test(method);
}

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      // Does this cookie string begin with the name we want?
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

function serverUpdate() {
  // const csrftoken = getCookie('csrftoken');
  const csrftoken = getCookie("csrftoken");

  // $.ajaxSetup({
  //     beforeSend: function (xhr, settings) {
  //         // if not safe, set csrftoken
  //         if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
  //             xhr.setRequestHeader("X-CSRFToken", csrftoken);
  //         }
  //     }
  // });

  var jsondata = new FormData();
  jsondata.append("responses", JSON.stringify(responses));
  jsondata.append("confidence", JSON.stringify(confidence));
  jsondata.append("start_times", JSON.stringify(start_times));
  jsondata.append("end_times", JSON.stringify(end_times));

  $.ajax({
    type: "POST",
    url: updateurl,
    contentType: false,
    cache: false,
    processData: false,
    dataType: "json",
    data: jsondata,
    headers: { "X-CSRFToken": csrftoken },
    dataType: "json",
    success: function (res, status) {},
    error: function (res) {
      // alert(res.status);
    },
  })
    .then((response) => {
      hues = JSON.parse(response.obscured);
      stimuli = JSON.parse(response.stimuli);
      last = JSON.parse(response.last);

      if (last) {
        location.href = goodbyeurl;
      }

      block_trial_number = 0;
      block_possible = 0;
      block_earned = 0;
      start_times = new Array();
      end_times = new Array();
      responses = new Array();
    })
    .then(() => {
      setTimeout(showStimulus, 2000);
    });
}

function hideAllElements() {
  document.querySelectorAll("div").forEach((div) => {
    div.style.display = "none";
  });
  document.querySelectorAll("h2").forEach((h2) => {
    h2.style.display = "none";
  });
  document.querySelectorAll("img").forEach((img) => {
    img.style.display = "none";
  });
}

function showStimulus() {
  hideAllElements();
  let stimulus_indx = stimuli[block_trial_number];
  document.querySelector(`#instructions`).style.display = "block";
  document.querySelector(`#stimulus_${stimulus_indx}`).style.display = "block";
  document.querySelector(`#image_shown`).style.display = "block";
  start_times.push(Date.now());
  listening_response = true;
}

function showConfidenceEstimate() {
  hideAllElements();
  document.querySelector(`#confidence_estimate`).style.display = "block";
  listening_confidence = true;
}

function scrub(dirty) {
  const dirty2 = [...dirty];
  let ncolumns = valid_keys_response.length;
  let nrows = dirty.length / ncolumns;
  let clean = [];
  while (dirty2.length) clean.push(dirty2.splice(0, ncolumns));
  let cntr = 0;
  for (i = 0; i < nrows; i++) {
    for (j = 0; j < ncolumns; j++) {
      clean[i][j] = Math.sqrt(atob(clean[i][j])) - cntr;
      cntr++;
    }
  }
  return clean;
}

function resultsSummary() {
  hideAllElements();

  let summary = document.querySelector(`#results_summary`);
  if (feedback_bool) {
    summary.innerHTML =
      "This block you earned " +
      block_earned +
      " of " +
      block_possible +
      " possible. In total, you have earned " +
      total_earned +
      " of " +
      total_possible +
      " possible.";
  } else {
    summary.innerHTML = "Storing the energy you've collected!";
  }
  summary.style.display = "block";

  serverUpdate();
}

function feedback(key_pressed) {
  hideAllElements();

  const clean = scrub(hues);
  let outcome =
    clean[block_trial_number][valid_keys_response.indexOf(key_pressed)];

  if (outcome == 1) {
    document.querySelector(`#feedback_correct`).style.display = "block";
    document.querySelector(`#rewarded_stim`).style.display = "block";
  } else {
    document.querySelector(`#feedback_incorrect`).style.display = "block";
    document.querySelector(`#nonrewarded_stim`).style.display = "block";
  }

  total_possible += Math.max.apply(Math, clean[block_trial_number]);
  block_possible += Math.max.apply(Math, clean[block_trial_number]);
  total_earned += outcome;
  block_earned += outcome;

  setTimeout(() => {
    if (block_trial_number == scrub(hues).length - 1) {
      resultsSummary();
    } else {
      block_trial_number++;
      showStimulus();
    }
  }, 1000);
}

function nofeedback(key_pressed) {
  hideAllElements();

  const clean = scrub(hues);
  let outcome =
    clean[block_trial_number][valid_keys_response.indexOf(key_pressed)];

  total_possible += Math.max.apply(Math, clean[block_trial_number]);
  block_possible += Math.max.apply(Math, clean[block_trial_number]);
  total_earned += outcome;
  block_earned += outcome;

  if (block_trial_number == scrub(hues).length - 1) {
    resultsSummary();
    // setTimeout( () => {
    //     resultsSummary();
    // }, 500);
  } else {
    block_trial_number++;
    showStimulus();
  }
}

document.addEventListener("DOMContentLoaded", function () {
  hideAllElements();
  document.querySelector(`#planet_intro`).style.display = "block";

  document.onkeydown = function (event) {
    let key_pressed = event.key;
    if (key_pressed && listening_intro) {
      listening_intro = false;
      showStimulus();
    } else if (
      key_pressed &&
      listening_response &&
      valid_keys_response.includes(key_pressed)
    ) {
      key_pressed_response = key_pressed;
      listening_response = false;
      end_times.push(Date.now());
      responses.push(key_pressed);
      showConfidenceEstimate();
    } else if (
      key_pressed &&
      listening_confidence &&
      valid_keys_confidence.includes(key_pressed)
    ) {
      key_pressed_confidence = key_pressed;
      listening_confidence = false;
      confidence.push(key_pressed_confidence);
      if (feedback_bool) {
        feedback(key_pressed_response);
      } else {
        nofeedback(key_pressed_response);
      }
    }
  };

  // setTimeout( () => {
  //         document.onkeydown = function(event) {
  //         let key_pressed = event.key;
  //         if (key_pressed && listening_response && valid_keys_response.includes(key_pressed)) {
  //             key_pressed_response = key_pressed
  //             listening_response = false
  //             end_times.push(Date.now())
  //             responses.push(key_pressed)
  //             showConfidenceEstimate()
  //         }
  //         else if (key_pressed && listening_confidence && valid_keys_confidence.includes(key_pressed)) {
  //             key_pressed_confidence = key_pressed
  //             listening_confidence = false
  //             confidence.push(key_pressed_confidence)
  //             if (feedback_bool) {
  //                 feedback(key_pressed_response)
  //             } else {
  //                 nofeedback(key_pressed_response)
  //             }
  //         }
  //     }
  //     showStimulus()
  // }, 10000);
});
