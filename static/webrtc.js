let pc;
let localStream;
const rtcConfig = {
  iceServers: [
    { urls: "stun:stun.l.google.com:19302" },
  ],
};

function waitForIceGatheringComplete(peerConnection) {
  if (peerConnection.iceGatheringState === "complete") {
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    function handleIceGatheringStateChange() {
      if (peerConnection.iceGatheringState === "complete") {
        peerConnection.removeEventListener("icegatheringstatechange", handleIceGatheringStateChange);
        resolve();
      }
    }

    peerConnection.addEventListener("icegatheringstatechange", handleIceGatheringStateChange);
  });
}

async function startCall() {
  const status = document.getElementById("status");
  const startButton = document.getElementById("startButton");

  startButton.disabled = true;
  status.textContent = "Requesting microphone access...";

  pc = new RTCPeerConnection(rtcConfig);

  pc.onconnectionstatechange = () => {
    status.textContent = `Peer connection: ${pc.connectionState}`;
    if (pc.connectionState === "failed") {
      startButton.disabled = false;
    }
  };

  pc.oniceconnectionstatechange = () => {
    console.log("iceConnectionState", pc.iceConnectionState);
  };

  pc.onicegatheringstatechange = () => {
    console.log("iceGatheringState", pc.iceGatheringState);
  };

  pc.onicecandidate = (event) => {
    if (event.candidate) {
      console.log("local candidate", event.candidate.candidate);
    } else {
      console.log("local candidate gathering complete");
    }
  };

  pc.ontrack = (event) => {
    const audio = document.getElementById("aiAudio");
    const [remoteStream] = event.streams;
    if (remoteStream) {
      audio.srcObject = remoteStream;
      status.textContent = "Receiving AI audio response...";
    }
  };

  localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
  localStream.getTracks().forEach((track) => {
    pc.addTrack(track, localStream);
  });
  pc.addTransceiver("audio", { direction: "recvonly" });

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  await waitForIceGatheringComplete(pc);

  status.textContent = "Sending WebRTC offer...";

  const response = await fetch("/offer/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      sdp: pc.localDescription.sdp,
      type: pc.localDescription.type,
    }),
  });

  if (!response.ok) {
    startButton.disabled = false;
    status.textContent = "Offer failed.";
    throw new Error(`Offer request failed: ${response.status}`);
  }

  const answer = await response.json();
  const remoteCandidates = (answer.sdp.match(/^a=candidate:/gm) || []).length;
  console.log("remote candidate count", remoteCandidates);
  console.log("remote SDP type", answer.type);
  await pc.setRemoteDescription(answer);

  status.textContent = "Negotiation complete. Speak for a few seconds...";
}

document.getElementById("startButton").addEventListener("click", () => {
  startCall().catch((error) => {
    document.getElementById("status").textContent = `Error: ${error.message}`;
    document.getElementById("startButton").disabled = false;
    console.error(error);
  });
});
