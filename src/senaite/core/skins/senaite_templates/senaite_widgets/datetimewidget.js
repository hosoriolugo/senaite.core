document.addEventListener("DOMContentLoaded", () => {

  class DateTimeWidget {

    constructor() {
      let datefields = document.querySelectorAll("input[type='date']");
      let timefields = document.querySelectorAll("input[type='time']");

      // bind event handlers
      this.update_date = this.update_date.bind(this);
      this.on_change = this.on_change.bind(this);

      // bind datefields
      datefields.forEach((el) => {
        el.addEventListener("change", this.on_change);
      });

      // bind timefields
      timefields.forEach((el) => {
        el.addEventListener("change", this.on_change);
      });

      // 🔹 AUTOFILL inicial al cargar la página
      this.autofill_now(datefields, timefields);
    }

    /**
     * set an input field value (if the field exists)
     */
    set_field(field, value) {
      if (!field) return;
      field.value = value;
    }

    /**
     * generate a full date w/o TZ from the date and time inputs
     */
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

    /**
     * event handler for `change` event
     */
    on_change(event) {
      let el = event.currentTarget;
      let target = el.getAttribute("target");

      let date = el.parentElement.querySelector("input[type='date']");
      let time = el.parentElement.querySelector("input[type='time']");
      let input = document.querySelector(`input[name='${target}']`);

      this.update_date(date, time, input);
    }

    /**
     * 🔹 Rellenar automáticamente fecha/hora actuales
     */
    autofill_now(datefields, timefields) {
      if (!datefields.length || !timefields.length) return;

      let now = new Date(); // hora local del navegador

      // formatear YYYY-MM-DD
      let yyyy = now.getFullYear();
      let mm = String(now.getMonth() + 1).padStart(2, "0");
      let dd = String(now.getDate()).padStart(2, "0");
      let dateStr = `${yyyy}-${mm}-${dd}`;

      // formatear HH:MM (24h)
      let hh = String(now.getHours()).padStart(2, "0");
      let min = String(now.getMinutes()).padStart(2, "0");
      let timeStr = `${hh}:${min}`;

      datefields.forEach((df) => (df.value = dateStr));
      timefields.forEach((tf) => (tf.value = timeStr));

      // 🔹 Actualiza también el input oculto que usa el widget
      timefields.forEach((tf) => {
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

