/**
The background page controls extension-level, window-level, and high-level tab functions
Functions starting with underscore(_) are not callable by the api. They are helper-functions only.
*/
var states = Object.freeze({READY: 1, BUSY: 2, ERROR: 3});
var state = states.READY;

var audio_success = new Audio();
audio_success.src = "audio/success.mp3";
var audio_fail = new Audio();
audio_fail.src = "audio/fail.wav";

var startPhrases = ["web jargon", "browser", "chrome"];
var stopPhrases = ["stop web jargon", "stop listening"];


var server;
var audioResponse;
var textResponse;
_loadOptions();

var keepListening = true;
var asked = false;

var recognition = new webkitSpeechRecognition();
recognition.continuous = true;
recognition.interimResults = true;

recognition.onerror = function(event) {
  //check if microphone is available
  if(event.error == 'not-allowed' && asked == false){
   asked = true;
   _getAudioPermission();
  }
}
recognition.onresult = function(event) {
  var final_transcript = "";
  var interim_transcript = "";
  for (var i = event.resultIndex; i < event.results.length; ++i) {
    if (event.results[i].isFinal) {
      final_transcript += event.results[i][0].transcript;
      var str = event.results[i][0].transcript;
      _processText(str);
    } else {
      interim_transcript += event.results[i][0].transcript;
    }
  }
}
recognition.onend = function() {
  if(keepListening){
    recognition.start();
  } else{
    listening = false;
  }
}
recognition.onstart = function(){
}

_startRecognition();

function _processText(str){
  str = str.trim();
  console.log(str);
  for(p in startPhrases){
    var phrase = startPhrases[p];
    var i = str.indexOf(phrase);
    if(i >= 0){
      var end = i+phrase.length;
      _sendText(str.substring(end, str.length));
      return;
    }
  }
}

function _sendText(str){
  chrome.tabs.query({active: true, currentWindow: true}, function (tabs) {
    var url;
    if (tabs != undefined) {
        url = tabs[0].url;
    } else {
        url = "www.google.com";
    }
    var key = (Math.random()*1e20).toString(36);
    _setBusy();
    var sendData = new Object();
    sendData.command = str;
    sendData.url = url;
    sendData.session_id = key;
    $.post( server, JSON.stringify(sendData), function( data ) {
      console.log(data);
      var cmd = JSON.parse(data)["action"];
      var func = cmd["action"];
      var params = cmd["arg_list"];
      if(func != null){
        var msg = _doCommand(func, params);
        _onSuccess(str, func, params);
      } else{
        _onError();
      }
    })
    .fail(function() {
      _setError();
      _doCommand("_addMessage",["Could not connect to server"]);
      audio_fail.play();
    });
  });
}

function _onError(){
  _setReady();
  if(audioResponse){
    audio_fail.play();
  }
  if(textResponse){
    _doCommand("_addMessage",["no match"]);
  }
}

function _onSuccess(inputStr, func, params){
  _setReady();
  if(audioResponse){
    audio_success.play(); 
  }
  if(textResponse){
    _doCommand("_addMessage",[func]);
  }
}

function openURL(u, currentTab){
  if(!currentTab){
   openTab(u);
   return;
  }
  chrome.tabs.query({active: true, currentWindow: true}, function (tabs) {
    chrome.tabs.update(tabs[0].id, {url: "www."+u+".com")});
  });
}

function openTab(u){
  if (u == undefined){
    u = "www.google.com";
  }
  chrome.tabs.create({url: "www."+u+".com")});
}

/**
Closes a tab
if input is number: Closes via index from left (0-start)
if input is string: Closes tabs which contain input string
*/
function closeTab(tabId){
  // do not execute action if tab id is undefined
  if(tabId == undefined){
    return;
  }
  if (typeof(tabId) == "number") {
    _closeTabAtIndex(tabId);
  } else if (typeof(tabId) == "string") {
    //tab id is a string
    chrome.tabs.query({currentWindow: true}, function (tabs) {
      for (t in tabs){
        lower_title = tabs[t].title.toLowerCase();
        if(lower_title.indexOf(tabId) > -1){
          chrome.tabs.remove(tabs[t].id);
        }
      }
    });
  }
  return;
}

/**
Switches active tab
if input is number: Chooses via index from left (0-start)
if input is string: Chooses first tab which contains input string
*/
function switchTab(tabId){
  // do not execute action if tab id is undefined
  if(tabId == undefined){
    return;
  }
  if (typeof(tabId) == "number") {
    chrome.tabs.query({currentWindow: true}, function (tabs) {
        if (0 < tabId && tabId <= tabs.length){
           chrome.tabs.update(tabs[tabId-1].id, {active: true});
        }
    });
  } else if (typeof(tabId) == "string") {
      //tab id is a string
      chrome.tabs.query({currentWindow: true}, function (tabs) {
        for (t in tabs){
          lower_title = tabs[t].title.toLowerCase();
          if(lower_title.indexOf(tabId) > -1){
            chrome.tabs.update(tabs[t].id, {active: true});
          }
        }
      });
  }
  return;
}

function displaySetup(){
  if (chrome.runtime.openOptionsPage) {
    // New way to open options pages, if supported (Chrome 42+).
    chrome.runtime.openOptionsPage();
  } else {
    // Reasonable fallback.
    window.open(chrome.runtime.getURL('options.html'));
  }
}

function displayHelp(show){
  var show = Boolean(show);
  if (show == true) {
      chrome.tabs.create({ url: "/html_help_pages/G_help_page.html" });
  } else {
     closeTab("help_page");
  }
}

function _closeFirstTab() {
    _closeTabAtIndex(0);
}

function _closeTabAtIndex(tabIndex) {
    chrome.tabs.query({active: true, currentWindow: true}, function (tabs) {
      if (0 < tabIndex && tabIndex <= tabs.length) {
        chrome.tabs.remove(tabs[tabIndex-1].id);
      }
    });
}

/**
Executes input command
Checks background page functions first, then checks current tab functions
*/
function _doCommand(cmd, params){
  if (typeof window[cmd] == 'function') { 
    window[cmd].apply(null, params);
    return;
  }
  //if function not found in background page, check content script
  chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
    chrome.tabs.sendMessage(tabs[0].id, {func : cmd, params : params}, function(response) {
      if(response){
        return response;
      }
  });
});
}

function _getAudioPermission(){
  window.open("chrome-extension://"+chrome.runtime.id+"/additional/requestAudio.html");
}

function _loadOptions(){
  //set defaults if needed
  if(localStorage["serverURL"] == undefined){
    localStorage["serverURL"] == "http://localhost:8080/";
  }
  if(localStorage["audioResponse"] == undefined){
    localStorage["audioResponse"] == true;
  }
  if(localStorage["textResponse"] == undefined){
    localStorage["textResponse"] == true;
  }
  server = localStorage["serverURL"];
  audioResponse = localStorage["audioResponse"] == "false" ? false : true;
  textResponse = localStorage["textResponse"] == "false" ? false : true;
}

function _getURL(name){
  var fullURL = "http://www."+name+".com";
  alert(_websiteExists(fullURL));
  return _websiteExists(fullURL) ? fullURL : "http://www.google.com/#q="+name;
}

function _websiteExists(url){
  var request;
  if(window.XMLHttpRequest){
    request = new XMLHttpRequest();
  }
  else{
    request = new ActiveXObject("Microsoft.XMLHTTP");
  }
  request.open('HEAD', url, false);
  request.send(); // there will be a 'pause' here until the response to come.
  // the object request will be actually modified
  if (request.status === 404) {
    return false;
  }
  return true;
}

function _startRecognition(){
  recognition.start();
}

function _setIcon(file){
  chrome.browserAction.setIcon({
    path: file
  });
}
function _setReady(){
  _setIcon("popup/plugin_ready.png");
  state = states.READY;
}
function _setBusy(){
  _setIcon("popup/plugin_busy.png");
  state = states.BUSY;
}
function _setError(){
  _setIcon("popup/plugin_error.png");
  state = states.ERROR;
}
