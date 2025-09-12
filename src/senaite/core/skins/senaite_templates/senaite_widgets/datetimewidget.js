document.addEventListener("DOMContentLoaded", () => {

  class DateTimeWidget {

    constructor() {
      this.update_date = this.update_date.bind(this);
      this.on_change = this.on_change.bind(this);
      this.waitForFields();
    }

    waitForFields() {
      let datefields = document.querySelectorAll("input[type='date']");
      let timefields = document.querySelectorAll("input[type='time']");
      if (datefields.length && timefields.length) {
        this.datefields = datefields;
        this.timefields = timefields;
        this.bind_fields();
        this.disable_autocomplete();
        this.autofill_now();
      } else {
        requestAnimationFrame(() => this.waitForFields());
      }
    }

    bind_fields() {
      this.datefields.forEach((el) => {
        el.addEventListener("change", this.on_change);
      });
      this.timefields.forEach((el) => {
        el.addEventListener("change", this.on_change);
      });
    }

    disable_autocomplete() {
      this.datefields.forEach((df) => df.setAttribute("autocomplete", "off"));
      this.timefields.forEach((tf) => tf.setAttribute("autocomplete", "off"));
    }

    set_field(field, value) {
      if (!field) return;
      field.value = value;
    }

    update_date(date, time, input) {
      let ds = date ? date.value : "";
      let ts = time ? time.value : "";

      this.set_field(date, ds);
      this.set_field(time, ts);

      if (ds && ts) {
        this.set_field(input, `${ds} ${ts}`);
      } else if (ds) {
        this.set_field(input, `${ds}`);
      } else {
        this.set_field(input, "");
      }
    }

    on_change(event) {
      let el = event.currentTarget;
      let target = el.getAttribute("target");
      let date = el.parentElement.querySelector("input[type='date']");
      let time = el.parentElement.querySelector("input[type='time']");
      let input = document.querySelector(`input[name='${target}']`);
      this.update_date(date, time, input);
    }

    autofill_now() {
      if (!this.datefields.length || !this.timefields.length) {
        console.warn("⚠️ DateTimeWidget: no encontró inputs date/time");
        return;
      }

      let now = new Date();
      let yyyy = now.getFullYear();
      let mm = String(now.getMonth() + 1).padStart(2, "0");
      let dd = String(now.getDate()).padStart(2, "0");
      let dateStr = `${yyyy}-${mm}-${dd}`;

      let hh = String(now.getHours()).padStart(2, "0");
      let min = String(now.getMinutes()).padStart(2, "0");
      let timeStr = `${hh}:${min}`;

      this.datefields.forEach((df) => (df.value = dateStr));
      this.timefields.forEach((tf) => (tf.value = timeStr));

      this.timefields.forEach((tf) => {
        let target = tf.getAttribute("target");
        if (target) {
          let hidden = document.querySelector(`input[name='${target}']`);
          this.update_date(tf.parentElement.querySelector("input[type='date']"), tf, hidden);
        }
      });
    }
  }

  new DateTimeWidget();
});
