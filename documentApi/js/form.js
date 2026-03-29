function hideElement(el) {
  if (el) {
    el.style.display = "none";
  }
}

function enableForm() {
  try {
    const handleButton = document.getElementById("cslider");
    if (handleButton) {
      handleButton.addEventListener("click", () => {
        const result = handleButton.getAttribute("unlockv");
        const resultInput = document.getElementById("result");
        if (resultInput) {
          resultInput.value = result ?? "";
        }
        hideElement(handleButton);
        document.querySelectorAll(".cslider-warn").forEach(hideElement);
        const sBtn = document.getElementById("sBtn");
        if (sBtn) {
          sBtn.style.display = "";
          sBtn.style.opacity = "1";
          sBtn.disabled = false;
        }
      });
    }
  } catch (e) {
    console.error(e);
  }
}

window.addEventListener("load", () => {
  enableForm();
});
