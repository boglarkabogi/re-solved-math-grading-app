(() => {
  "use strict";
  // Frontend-only demo data. Nothing is written to Django's database.
  const initialCourses = [
    { id: 1, name: "Discrete Mathematics", term: "2026/27/1", group: "Group 01", code: "MATH42", students: 28, lessons: [{name:"Divisibility",state:"Open"},{name:"Linear congruences",state:"Planned"},{name:"Polynomial GCD",state:"Planned"}] },
    { id: 2, name: "Discrete Mathematics", term: "2026/27/1", group: "Group 02", code: "ALG728", students: 24, lessons: [{name:"Divisibility",state:"Closed"},{name:"Linear congruences",state:"Open"}] }
  ];
  const initialTasks = [
    {code:"DIV-001",topic:"Divisibility",description:"Find the greatest common divisor of 84 and 126.",solution:"GCD = 42",availability:"Class and practice"},
    {code:"DIV-002",topic:"Divisibility",description:"Determine whether 17 divides 357.",solution:"Yes, 357 = 17 × 21",availability:"Class only"},
    {code:"CON-001",topic:"Linear congruences",description:"Solve 3x ≡ 6 (mod 9).",solution:"x ≡ 2 (mod 3)",availability:"Class and practice"},
    {code:"POL-001",topic:"Polynomial GCD",description:"Find the GCD of the given polynomials.",solution:"Sample solution",availability:"Practice only"}
  ];
  const submissions = [
    {student:"Anna Kovács",neptun:"ABC123",course:"Group 01",lesson:"Divisibility",status:"Evaluated",score:"1.75 / 2"},
    {student:"Bence Nagy",neptun:"DEF456",course:"Group 01",lesson:"Divisibility",status:"Pending review",score:"—"},
    {student:"Lilla Tóth",neptun:"GHI789",course:"Group 02",lesson:"Linear congruences",status:"Evaluated",score:"2 / 2"},
    {student:"Máté Kiss",neptun:"JKL012",course:"Group 02",lesson:"Linear congruences",status:"Not submitted",score:"—"}
  ];
  const courses = structuredClone(initialCourses), tasks = structuredClone(initialTasks);
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const makeCode = () => { let code; do { code = Array.from({length:6},()=>"ABCDEFGHJKLMNPQRSTUVWXYZ23456789"[Math.floor(Math.random()*32)]).join(''); } while(courses.some(c=>c.code===code)); return code; };

  function renderCourses() {
    $("#teacher-course-list").innerHTML = courses.map(c => `
      <article class="teacher-course"><div class="teacher-course-header"><div><h3>${escapeHtml(c.name)}</h3><p class="teacher-muted">${escapeHtml(c.group)} · ${escapeHtml(c.term)}</p></div>
      <div class="teacher-course-right"><span class="teacher-muted">${c.students} students</span><button type="button" class="teacher-link-button" data-toggle-course="${c.id}" aria-expanded="false">View details ▾</button></div></div>
      <div class="teacher-course-detail" id="teacher-course-${c.id}" hidden><div class="teacher-detail-grid"><div><span class="teacher-detail-label">Course</span><span class="teacher-detail-value">${escapeHtml(c.name)}</span></div><div><span class="teacher-detail-label">Group</span><span class="teacher-detail-value">${escapeHtml(c.group)}</span></div><div><span class="teacher-detail-label">JOINING CODE</span><span class="teacher-detail-value teacher-code">${escapeHtml(c.code)}</span> <button class="teacher-link-button" type="button" data-copy="${escapeHtml(c.code)}">Copy</button></div></div>
      <div class="teacher-lessons"><div class="teacher-lessons-heading"><h4>Lessons</h4><button type="button" class="teacher-link-button" data-add-lesson="${c.id}">+ Add lesson</button></div><div>${c.lessons.length ? c.lessons.map((l,i)=>`<div class="teacher-lesson-row"><span>Lesson ${String(i+1).padStart(2,'0')} · ${escapeHtml(l.name)}</span><span class="teacher-status">${escapeHtml(l.state)}</span></div>`).join('') : '<p class="teacher-empty">No lessons created yet.</p>'}</div></div></div></article>`).join('');
  }
  function renderTasks() {
    const topic = $("#teacher-topic-filter").value;
    const visible = tasks.filter(t=>topic==='all'||t.topic===topic);
    $("#teacher-task-count").textContent = `${visible.length} tasks`;
    $("#teacher-task-body").innerHTML = visible.length ? visible.map(t=>`<tr><td>${escapeHtml(t.code)}</td><td class="teacher-description" title="${escapeHtml(t.description)}">${escapeHtml(t.description)}</td><td>${escapeHtml(t.topic)}</td><td><span class="teacher-status">${escapeHtml(t.availability)}</span></td><td><button class="teacher-link-button" type="button" data-task="${escapeHtml(t.code)}">View</button></td></tr>`).join('') : '<tr><td colspan="5" class="teacher-empty">No tasks in this topic.</td></tr>';
  }
  function renderSubmissions() {
    const status = $("#teacher-submission-filter").value;
    const visible = submissions.filter(s=>status==='all'||s.status===status);
    $("#teacher-submission-body").innerHTML = visible.length ? visible.map(s=>`<tr><td>${escapeHtml(s.student)}</td><td>${escapeHtml(s.neptun)}</td><td>${escapeHtml(s.course)}</td><td>${escapeHtml(s.lesson)}</td><td><span class="teacher-status">${escapeHtml(s.status)}</span></td><td>${escapeHtml(s.score)}</td><td><button class="teacher-link-button" type="button" data-submission="${escapeHtml(s.student)}">Details</button></td></tr>`).join('') : '<tr><td colspan="7" class="teacher-empty">No submissions with this status.</td></tr>';
  }
  function openModal(kind) {
    $("#teacher-modal-title").textContent = kind==='course' ? 'Create course' : 'Add task';
    $("#teacher-course-form").hidden = kind!=='course'; $("#teacher-task-form").hidden = kind!=='task';
    $("#teacher-modal").hidden = false;
    $(kind==='course'?'#teacher-course-form input':'#teacher-task-form input').focus();
  }
  function closeModal() { $("#teacher-modal").hidden = true; }
  document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>{
    document.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('is-active',b===button);b.setAttribute('aria-selected',String(b===button));});
    document.querySelectorAll('[data-panel]').forEach(p=>p.hidden=p.dataset.panel!==button.dataset.tab);
  }));
  document.querySelectorAll('[data-open]').forEach(b=>b.addEventListener('click',()=>openModal(b.dataset.open)));
  $("#teacher-modal-close").addEventListener('click',closeModal);
  document.querySelectorAll('[data-close]').forEach(b=>b.addEventListener('click',closeModal));
  $("#teacher-modal").addEventListener('click',e=>{if(e.target===$("#teacher-modal"))closeModal();});
  document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});
  $("#teacher-course-form").addEventListener('submit',e=>{
    e.preventDefault(); const f=new FormData(e.target);
    courses.push({id:Math.max(...courses.map(c=>c.id),0)+1,name:f.get('name').trim(),term:f.get('term').trim(),group:f.get('group').trim(),code:makeCode(),students:0,lessons:[]});
    e.target.reset();closeModal();renderCourses();
  });
  $("#teacher-task-form").addEventListener('submit',e=>{
    e.preventDefault();const f=new FormData(e.target);const code=f.get('code').trim();
    if(tasks.some(t=>t.code.toLowerCase()===code.toLowerCase())){alert('A task with this code already exists.');return;}
    tasks.push({code,topic:f.get('topic'),description:f.get('description').trim(),solution:f.get('solution').trim(),availability:f.get('availability')});
    e.target.reset();closeModal();renderTasks();
  });
  $("#teacher-topic-filter").addEventListener('change',renderTasks);
  $("#teacher-submission-filter").addEventListener('change',renderSubmissions);
  $("#teacher-course-list").addEventListener('click',e=>{
    const toggle=e.target.closest('[data-toggle-course]');
    if(toggle){const panel=document.getElementById(`teacher-course-${toggle.dataset.toggleCourse}`);panel.hidden=!panel.hidden;toggle.setAttribute('aria-expanded',String(!panel.hidden));toggle.textContent=panel.hidden?'View details ▾':'Hide details ▴';return;}
    const copy=e.target.closest('[data-copy]');if(copy){if(navigator.clipboard?.writeText){navigator.clipboard.writeText(copy.dataset.copy).then(()=>{copy.textContent='Copied';}).catch(()=>prompt('Copy joining code:',copy.dataset.copy));}else{prompt('Copy joining code:',copy.dataset.copy);}return;}
    const lesson=e.target.closest('[data-add-lesson]');if(lesson){const course=courses.find(c=>c.id===Number(lesson.dataset.addLesson));const name=prompt('Lesson name (demo only):');if(name?.trim()){course.lessons.push({name:name.trim(),state:'Planned'});renderCourses();document.getElementById(`teacher-course-${course.id}`).hidden=false;} }
  });
  $("#teacher-task-body").addEventListener('click',e=>{const b=e.target.closest('[data-task]');if(!b)return;const t=tasks.find(x=>x.code===b.dataset.task);if(t)alert(`${t.code} — ${t.topic}\n\n${t.description}\n\nCorrect solution:\n${t.solution}`);});
  $("#teacher-submission-body").addEventListener('click',e=>{const b=e.target.closest('[data-submission]');if(b)alert('Demo only: submission details will be connected to Django later.');});
  renderCourses();renderTasks();renderSubmissions();
})();
