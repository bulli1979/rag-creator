function onReady(fn) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", fn);
  } else {
    fn();
  }
}

onReady(() => {
  document.querySelectorAll(".carousel").forEach((carousel) => {
    Carousel.init(carousel);
  });
  document.querySelectorAll(".feedlist").forEach((feed) => {
    Feeds.init(feed);
  });
});

class Carousel {
  constructor() {}

  static init(carousel) {
    const id = carousel.getAttribute("id");
    if (!id) {
      return;
    }
    const items = carousel.querySelectorAll(".carousel-indicators li");
    const carouselItems = [];
    items.forEach((item, i) => {
      item.setAttribute("data-target", "#" + id);
      if (i === 0) {
        item.classList.add("active");
      }
      const carouselItem =
        '<div class="carousel-item' + (i === 0 ? " active" : "") + '">' +
        '<img src="' +
        (item.getAttribute("image") ?? "") +
        '" class="d-block w-100" alt="' +
        (item.getAttribute("imageAlt") ?? "") +
        '" />' +
        '<div class="carousel-caption d-none d-md-block">' +
        " <h5>" +
        (item.getAttribute("slidelabel") ?? "") +
        "</h5>" +
        "<p>" +
        (item.getAttribute("slidetext") ?? "") +
        "</p></div></div>";
      carouselItems.push(carouselItem);
    });
    const inner = carousel.querySelector(".carousel-inner");
    if (inner) {
      inner.innerHTML = carouselItems.join("");
    }
  }
}

class Feeds {
  constructor() {}

  static init(feed) {
    const feedfile = feed.getAttribute("id");
    if (!feedfile) {
      return;
    }
    const request = new XMLHttpRequest();
    request.open("GET", "/" + feedfile);
    request.addEventListener("load", () => {
      if (request.status >= 200 && request.status < 300) {
        try {
          const feedresponse = JSON.parse(request.responseText);
          const feeds = feedresponse.lst.sort((a, b) => {
            const d1 = new Date(a.dt).getTime();
            const d2 = new Date(b.dt).getTime();
            return d2 - d1;
          });
          Feeds.displayFeeds(feeds, feed);
        } catch (err) {
          console.warn("Feed JSON parse error", err);
        }
      } else {
        console.warn(request.statusText, request.responseText);
      }
    });
    request.send();
  }

  static displayFeeds(feeds, feed) {
    const countAttr = feed.getAttribute("count");
    if (countAttr) {
      const n = parseInt(countAttr, 10);
      if (!Number.isNaN(n)) {
        feeds = feeds.slice(0, n);
      }
    }
    feeds.forEach((feedentry) => {
      const div = document.createElement("div");
      div.innerHTML =
        '<a href="' +
        feedentry.opath +
        '"><h4><span>' +
        Tools.createDateString(feedentry.dt) +
        "</span>" +
        feedentry.title +
        "</h4><div>" +
        Feeds.getDescr(feedentry.descr) +
        "</div></a><hr>";
      feed.appendChild(div);
    });
    const showlink = feed.getAttribute("showlink");
    if (showlink) {
      const link = feed.getAttribute("link");
      const linktitle = feed.getAttribute("linktitle");
      const linkdiv = document.createElement("div");
      linkdiv.innerHTML = '<a href="' + link + '">' + linktitle + "</a>";
      feed.appendChild(linkdiv);
    }
  }

  static getDescr(descr) {
    const split = descr.split(" ");
    let descrText = "";
    let count = 0;
    split.forEach((sub) => {
      count += sub.length + 1;
      if (count < 80) {
        descrText += sub + " ";
      }
    });
    return descrText + (descr.length > 80 ? " ..." : "");
  }
}

class Tools {
  constructor() {}

  static createDateString(date) {
    const d = new Date(date);
    let year = d.getFullYear();
    let month = d.getMonth() + 1 + "";
    month = month.length === 1 ? "0" + month : month;
    let day = d.getDate() + "";
    day = day.length === 1 ? "0" + day : day;
    return "" + day + "." + month + "." + year;
  }
}
