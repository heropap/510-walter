import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import BacterialJourneyGame from "../../bacterial_journey_game.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BacterialJourneyGame />
  </StrictMode>
);
