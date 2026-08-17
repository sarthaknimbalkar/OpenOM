// openOM popup — badge + card + publish UI lands in Task 5.
import { honestLabel } from "openom-js";

const app = document.getElementById("app");
if (app) app.textContent = honestLabel("absent").label;
