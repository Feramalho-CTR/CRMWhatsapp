import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyAwpBfjx7jMYOk1LGrmgTFPeQmPEltIWJ4",
  authDomain: "crmwhatsapp-f50bb.firebaseapp.com",
  databaseURL: "https://crmwhatsapp-f50bb-default-rtdb.firebaseio.com",
  projectId: "crmwhatsapp-f50bb",
  storageBucket: "crmwhatsapp-f50bb.firebasestorage.app",
  messagingSenderId: "447807832727",
  appId: "1:447807832727:web:4955ffe60b2d4928dddfd2"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
