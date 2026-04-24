import type {
  Alert,
  Camera,
  DashboardOverview,
  Employee,
  EmployeeAttendanceDay,
  EmployeeDaySummary,
  EmployeeFaceProfile,
  EmployeeReport,
  EmployeeTimelineItem,
  EmployeeZoneVisitStat,
  KnownPerson,
  KnownPersonFaceProfile,
  LiveMonitorStatus,
  ModeTemplate,
  Rule,
  Site,
  User,
  WorkerAssignment,
  Zone,
} from '../types/models'

const OFFICE_SITE_ID = 'site-office-demo'
const HOME_SITE_ID = 'site-home-demo'

const OFFICE_GATE_CAMERA_ID = 'cam-office-gate'
const OFFICE_FLOOR_CAMERA_ID = 'cam-office-floor'
const HOME_GATE_CAMERA_ID = 'cam-home-gate'

const SERVER_ROOM_ZONE_ID = 'zone-server-room'
const SMOKING_ZONE_ID = 'zone-smoking-area'
const FLOOR_ZONE_ID = 'zone-main-floor'
const HOME_ENTRY_ZONE_ID = 'zone-home-entry'
const HOME_LIVING_ZONE_ID = 'zone-home-living'

const EMPLOYEE_AARAV_ID = 'employee-aarav'
const EMPLOYEE_RIYA_ID = 'employee-riya'
const KNOWN_PERSON_MRS_SHARMA_ID = 'known-mrs-sharma'
const KNOWN_PERSON_CARETAKER_ID = 'known-caretaker'

const NOW = '2026-04-24T11:10:00+05:30'
const WINDOW_START = '2026-04-18T00:00:00+05:30'

function svgDataUri(markup: string) {
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(markup)}`
}

function createSceneImage(
  title: string,
  subtitle: string,
  accent: string,
  badges: string[],
) {
  const badgeMarkup = badges
    .map(
      (badge, index) => `
        <g transform="translate(${48 + index * 190}, 592)">
          <rect width="164" height="44" rx="22" fill="rgba(11, 17, 18, 0.78)" stroke="rgba(255,255,255,0.18)" />
          <text x="82" y="28" text-anchor="middle" fill="#f4efe6" font-size="18" font-family="Segoe UI, sans-serif">${badge}</text>
        </g>`,
    )
    .join('')

  return svgDataUri(`
    <svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#122224" />
          <stop offset="100%" stop-color="#23373a" />
        </linearGradient>
        <linearGradient id="floor" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="${accent}" stop-opacity="0.12" />
          <stop offset="100%" stop-color="#de6e45" stop-opacity="0.16" />
        </linearGradient>
      </defs>
      <rect width="1280" height="720" fill="url(#bg)" />
      <rect x="40" y="40" width="1200" height="640" rx="28" fill="rgba(4, 9, 10, 0.18)" stroke="rgba(255,255,255,0.12)" />
      <rect x="82" y="126" width="1118" height="460" rx="20" fill="rgba(244,239,230,0.05)" stroke="rgba(255,255,255,0.08)" />
      <rect x="122" y="182" width="360" height="270" rx="20" fill="rgba(26,164,132,0.10)" stroke="rgba(26,164,132,0.55)" />
      <rect x="780" y="204" width="250" height="192" rx="20" fill="rgba(220,108,85,0.10)" stroke="rgba(220,108,85,0.55)" />
      <rect x="560" y="454" width="214" height="78" rx="16" fill="rgba(227,163,77,0.14)" stroke="rgba(227,163,77,0.55)" />
      <circle cx="310" cy="310" r="44" fill="rgba(244,239,230,0.92)" />
      <circle cx="312" cy="270" r="22" fill="#1aa484" />
      <rect x="277" y="295" width="70" height="88" rx="22" fill="#1aa484" />
      <circle cx="424" cy="328" r="40" fill="rgba(244,239,230,0.92)" />
      <circle cx="426" cy="292" r="20" fill="#de6e45" />
      <rect x="394" y="316" width="64" height="82" rx="20" fill="#de6e45" />
      <rect x="856" y="300" width="116" height="62" rx="18" fill="rgba(244,239,230,0.85)" />
      <rect x="0" y="520" width="1280" height="200" fill="url(#floor)" />
      <text x="72" y="92" fill="#f4efe6" font-size="34" font-family="Segoe UI, sans-serif" font-weight="700">${title}</text>
      <text x="72" y="126" fill="#b8b0a0" font-size="20" font-family="Segoe UI, sans-serif">${subtitle}</text>
      ${badgeMarkup}
    </svg>
  `)
}

function createPortrait(label: string, caption: string, accent: string) {
  return svgDataUri(`
    <svg xmlns="http://www.w3.org/2000/svg" width="320" height="320" viewBox="0 0 320 320">
      <defs>
        <linearGradient id="portrait" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="${accent}" />
          <stop offset="100%" stop-color="#101819" />
        </linearGradient>
      </defs>
      <rect width="320" height="320" rx="36" fill="url(#portrait)" />
      <circle cx="160" cy="124" r="56" fill="rgba(244,239,230,0.92)" />
      <rect x="94" y="176" width="132" height="92" rx="42" fill="rgba(244,239,230,0.92)" />
      <text x="160" y="142" text-anchor="middle" fill="${accent}" font-size="34" font-family="Segoe UI, sans-serif" font-weight="700">${label}</text>
      <text x="160" y="294" text-anchor="middle" fill="#f4efe6" font-size="22" font-family="Segoe UI, sans-serif">${caption}</text>
    </svg>
  `)
}

const officeFrame = createSceneImage(
  'Office Gate Feed',
  'Local worker demo frame with live detections and zone overlays',
  '#1aa484',
  ['2 employees', '1 visitor', '1 restricted zone'],
)

const homeFrame = createSceneImage(
  'Home Entry Feed',
  'Demo frame showing gate coverage for known-person vs unknown-person alerts',
  '#e3a34d',
  ['gate zone', 'known person', 'visitor alert'],
)

const faceAarav = createPortrait('AM', 'Aarav', '#1aa484')
const faceRiya = createPortrait('RS', 'Riya', '#de6e45')
const faceMrsSharma = createPortrait('MS', 'Mrs Sharma', '#e3a34d')
const faceCaretaker = createPortrait('RK', 'Ravi', '#1aa484')

const sites: Site[] = [
  {
    id: OFFICE_SITE_ID,
    name: 'Indore Office',
    site_type: 'office',
    timezone: 'Asia/Calcutta',
    description: 'Staff attendance, restricted areas, and rule-based alerting demo.',
    is_active: true,
  },
  {
    id: HOME_SITE_ID,
    name: 'Palasia Home',
    site_type: 'home',
    timezone: 'Asia/Calcutta',
    description: 'Home safety demo with gate alerts and trusted-known-person recognition.',
    is_active: true,
  },
]

const admins: User[] = [
  {
    id: 'admin-yash',
    email: 'admin@detectionai.demo',
    full_name: 'Yash Sachdev',
    role: 'admin',
    is_active: true,
  },
  {
    id: 'admin-ops',
    email: 'ops@detectionai.demo',
    full_name: 'Operations Lead',
    role: 'admin',
    is_active: true,
  },
]

const camerasBySite: Record<string, Camera[]> = {
  [OFFICE_SITE_ID]: [
    {
      id: OFFICE_GATE_CAMERA_ID,
      site_id: OFFICE_SITE_ID,
      name: 'Front Gate Camera',
      source_type: 'droidcam',
      source_value: '192.168.1.44:4747',
      is_enabled: true,
    },
    {
      id: OFFICE_FLOOR_CAMERA_ID,
      site_id: OFFICE_SITE_ID,
      name: 'Main Floor Camera',
      source_type: 'rtsp',
      source_value: 'rtsp://office-floor.local/stream',
      is_enabled: true,
    },
  ],
  [HOME_SITE_ID]: [
    {
      id: HOME_GATE_CAMERA_ID,
      site_id: HOME_SITE_ID,
      name: 'Gate Camera',
      source_type: 'webcam',
      source_value: '0',
      is_enabled: true,
    },
  ],
}

const zonesBySite: Record<string, Zone[]> = {
  [OFFICE_SITE_ID]: [
    {
      id: SERVER_ROOM_ZONE_ID,
      site_id: OFFICE_SITE_ID,
      name: 'Server Room',
      zone_type: 'restricted',
      color: '#dc6c55',
      is_restricted: true,
      points: [
        { x: 790, y: 205 },
        { x: 1032, y: 205 },
        { x: 1032, y: 400 },
        { x: 790, y: 400 },
      ],
    },
    {
      id: SMOKING_ZONE_ID,
      site_id: OFFICE_SITE_ID,
      name: 'Smoking Area',
      zone_type: 'smoking_area',
      color: '#e3a34d',
      is_restricted: true,
      points: [
        { x: 555, y: 452 },
        { x: 776, y: 452 },
        { x: 776, y: 537 },
        { x: 555, y: 537 },
      ],
    },
    {
      id: FLOOR_ZONE_ID,
      site_id: OFFICE_SITE_ID,
      name: 'Main Floor',
      zone_type: 'work_area',
      color: '#1aa484',
      is_restricted: false,
      points: [
        { x: 118, y: 182 },
        { x: 490, y: 182 },
        { x: 490, y: 454 },
        { x: 118, y: 454 },
      ],
    },
  ],
  [HOME_SITE_ID]: [
    {
      id: HOME_ENTRY_ZONE_ID,
      site_id: HOME_SITE_ID,
      name: 'Front Gate',
      zone_type: 'entry',
      color: '#e3a34d',
      is_restricted: false,
      points: [
        { x: 784, y: 214 },
        { x: 1026, y: 214 },
        { x: 1026, y: 406 },
        { x: 784, y: 406 },
      ],
    },
    {
      id: HOME_LIVING_ZONE_ID,
      site_id: HOME_SITE_ID,
      name: 'Living Room',
      zone_type: 'general',
      color: '#1aa484',
      is_restricted: false,
      points: [
        { x: 118, y: 186 },
        { x: 486, y: 186 },
        { x: 486, y: 454 },
        { x: 118, y: 454 },
      ],
    },
  ],
}

const rulesBySite: Record<string, Rule[]> = {
  [OFFICE_SITE_ID]: [
    {
      id: 'rule-office-server-room',
      site_id: OFFICE_SITE_ID,
      applies_to_site_type: null,
      template_key: 'person_in_server_room',
      name: 'Unknown Person In Server Room',
      description: 'Trigger a high alert when an unrecognized person enters the server room.',
      conditions: {
        entity_type: 'person',
        zone_id: SERVER_ROOM_ZONE_ID,
      },
      actions: {
        create_alert: true,
        snapshot: true,
      },
      severity: 'critical',
      is_default: false,
      is_enabled: true,
    },
    {
      id: 'rule-office-smoking',
      site_id: OFFICE_SITE_ID,
      applies_to_site_type: null,
      template_key: 'employee_in_smoking_area',
      name: 'Employee In Smoking Area',
      description: 'Raise a high alert when a recognized employee enters the smoking area.',
      conditions: {
        entity_type: 'employee',
        zone_id: SMOKING_ZONE_ID,
      },
      actions: {
        create_alert: true,
        snapshot: true,
      },
      severity: 'high',
      is_default: false,
      is_enabled: true,
    },
  ],
  [HOME_SITE_ID]: [
    {
      id: 'rule-home-gate-unknown',
      site_id: HOME_SITE_ID,
      applies_to_site_type: null,
      template_key: 'unknown_person_at_gate',
      name: 'Unknown Person At Gate',
      description: 'Raise an alert whenever an unknown person appears inside the gate entry zone.',
      conditions: {
        entity_type: 'person',
        zone_id: HOME_ENTRY_ZONE_ID,
      },
      actions: {
        create_alert: true,
        snapshot: true,
      },
      severity: 'critical',
      is_default: true,
      is_enabled: true,
    },
  ],
}

const employeeFaceProfiles: Record<string, EmployeeFaceProfile[]> = {
  [EMPLOYEE_AARAV_ID]: [
    {
      id: 'face-aarav-1',
      employee_id: EMPLOYEE_AARAV_ID,
      source_image_path: faceAarav,
    },
  ],
  [EMPLOYEE_RIYA_ID]: [
    {
      id: 'face-riya-1',
      employee_id: EMPLOYEE_RIYA_ID,
      source_image_path: faceRiya,
    },
  ],
}

const employeesBySite: Record<string, Employee[]> = {
  [OFFICE_SITE_ID]: [
    {
      id: EMPLOYEE_AARAV_ID,
      site_id: OFFICE_SITE_ID,
      employee_code: 'EMP-104',
      first_name: 'Aarav',
      last_name: 'Mehta',
      role_title: 'Operations Analyst',
      is_active: true,
      shift_name: 'Day Shift',
      shift_start_time: '09:00',
      shift_end_time: '17:00',
      shift_grace_minutes: 10,
      shift_days: ['mon', 'tue', 'wed', 'thu', 'fri'],
      face_profiles: employeeFaceProfiles[EMPLOYEE_AARAV_ID],
    },
    {
      id: EMPLOYEE_RIYA_ID,
      site_id: OFFICE_SITE_ID,
      employee_code: 'EMP-118',
      first_name: 'Riya',
      last_name: 'Sharma',
      role_title: 'Support Engineer',
      is_active: true,
      shift_name: 'Day Shift',
      shift_start_time: '10:00',
      shift_end_time: '18:00',
      shift_grace_minutes: 10,
      shift_days: ['mon', 'tue', 'wed', 'thu', 'fri'],
      face_profiles: employeeFaceProfiles[EMPLOYEE_RIYA_ID],
    },
  ],
  [HOME_SITE_ID]: [],
}

const knownPersonFaceProfiles: Record<string, KnownPersonFaceProfile[]> = {
  [KNOWN_PERSON_MRS_SHARMA_ID]: [
    {
      id: 'known-face-1',
      known_person_id: KNOWN_PERSON_MRS_SHARMA_ID,
      source_image_path: faceMrsSharma,
    },
  ],
  [KNOWN_PERSON_CARETAKER_ID]: [
    {
      id: 'known-face-2',
      known_person_id: KNOWN_PERSON_CARETAKER_ID,
      source_image_path: faceCaretaker,
    },
  ],
}

const knownPeopleBySite: Record<string, KnownPerson[]> = {
  [HOME_SITE_ID]: [
    {
      id: KNOWN_PERSON_MRS_SHARMA_ID,
      site_id: HOME_SITE_ID,
      display_name: 'Mrs Sharma',
      notes: 'Family member',
      is_active: true,
      face_profiles: knownPersonFaceProfiles[KNOWN_PERSON_MRS_SHARMA_ID],
    },
    {
      id: KNOWN_PERSON_CARETAKER_ID,
      site_id: HOME_SITE_ID,
      display_name: 'Ravi',
      notes: 'Caretaker who visits every morning',
      is_active: true,
      face_profiles: knownPersonFaceProfiles[KNOWN_PERSON_CARETAKER_ID],
    },
  ],
  [OFFICE_SITE_ID]: [],
}

const alertsBySite: Record<string, Alert[]> = {
  [OFFICE_SITE_ID]: [
    {
      id: 'alert-office-1',
      site_id: OFFICE_SITE_ID,
      camera_id: OFFICE_GATE_CAMERA_ID,
      rule_id: 'rule-office-smoking',
      event_id: 'event-office-1',
      title: 'Employee In Smoking Area',
      description: 'Riya Sharma entered the smoking area during an active shift window.',
      severity: 'high',
      status: 'open',
      snapshot_path: officeFrame,
      occurred_at: '2026-04-24T10:58:00+05:30',
      details: {
        zone_name: 'Smoking Area',
        employee_code: 'EMP-118',
        identity: 'Riya Sharma',
        repeat_count: 3,
        first_seen_at: '2026-04-24T10:54:00+05:30',
        last_seen_at: '2026-04-24T10:58:00+05:30',
      },
    },
    {
      id: 'alert-office-2',
      site_id: OFFICE_SITE_ID,
      camera_id: OFFICE_FLOOR_CAMERA_ID,
      rule_id: 'rule-office-server-room',
      event_id: 'event-office-2',
      title: 'Unknown Person In Server Room',
      description: 'An unrecognized visitor appeared inside the restricted server room zone.',
      severity: 'critical',
      status: 'acknowledged',
      snapshot_path: officeFrame,
      occurred_at: '2026-04-24T09:42:00+05:30',
      details: {
        zone_name: 'Server Room',
        subject_label: 'Unknown person',
        repeat_count: 1,
        first_seen_at: '2026-04-24T09:42:00+05:30',
        last_seen_at: '2026-04-24T09:42:00+05:30',
      },
    },
  ],
  [HOME_SITE_ID]: [
    {
      id: 'alert-home-1',
      site_id: HOME_SITE_ID,
      camera_id: HOME_GATE_CAMERA_ID,
      rule_id: 'rule-home-gate-unknown',
      event_id: 'event-home-1',
      title: 'Unknown Person At Gate',
      description: 'An unrecognized visitor appeared inside the gate entry zone.',
      severity: 'critical',
      status: 'open',
      snapshot_path: homeFrame,
      occurred_at: '2026-04-24T08:15:00+05:30',
      details: {
        zone_name: 'Front Gate',
        subject_label: 'Unknown person',
        repeat_count: 2,
        first_seen_at: '2026-04-24T08:12:00+05:30',
        last_seen_at: '2026-04-24T08:15:00+05:30',
      },
    },
    {
      id: 'alert-home-2',
      site_id: HOME_SITE_ID,
      camera_id: HOME_GATE_CAMERA_ID,
      rule_id: null,
      event_id: 'event-home-2',
      title: 'Known Person Recognized',
      description: 'Mrs Sharma was recognized at the gate, so no visitor escalation was needed.',
      severity: 'low',
      status: 'closed',
      snapshot_path: homeFrame,
      occurred_at: '2026-04-23T19:22:00+05:30',
      details: {
        zone_name: 'Front Gate',
        identity: 'Mrs Sharma',
        repeat_count: 1,
        first_seen_at: '2026-04-23T19:22:00+05:30',
        last_seen_at: '2026-04-23T19:22:00+05:30',
      },
    },
  ],
}

const dashboardOverviewBySite: Record<string, DashboardOverview> = {
  [OFFICE_SITE_ID]: {
    stats: [
      { key: 'cameras', label: 'Active Cameras', value: 2 },
      { key: 'rules', label: 'Active Rules', value: 2 },
      { key: 'employees', label: 'Tracked Employees', value: 2 },
      { key: 'alerts', label: 'Alerts Today', value: 2 },
    ],
    recent_alerts: alertsBySite[OFFICE_SITE_ID],
  },
  [HOME_SITE_ID]: {
    stats: [
      { key: 'cameras', label: 'Active Cameras', value: 1 },
      { key: 'rules', label: 'Active Rules', value: 1 },
      { key: 'known_people', label: 'Known People', value: 2 },
      { key: 'alerts', label: 'Alerts Today', value: 1 },
    ],
    recent_alerts: alertsBySite[HOME_SITE_ID],
  },
}

const modeTemplates: ModeTemplate[] = [
  {
    site_type: 'office',
    label: 'Office',
    description: 'Designed for employee monitoring, restricted areas, posture alerts, and attendance reporting.',
    rules: [
      {
        template_key: 'employee_in_smoking_area',
        name: 'Employee In Smoking Area',
        description: 'Alert when a recognized employee enters a smoking zone.',
        severity: 'high',
      },
      {
        template_key: 'unknown_person_in_restricted_zone',
        name: 'Unknown Person In Restricted Zone',
        description: 'Alert when an unrecognized person enters a restricted zone.',
        severity: 'critical',
      },
    ],
  },
  {
    site_type: 'home',
    label: 'Home',
    description: 'Designed for known-vs-unknown recognition and gate-focused visitor safety.',
    rules: [
      {
        template_key: 'unknown_person_at_gate',
        name: 'Unknown Person At Gate',
        description: 'Alert when an unknown person appears inside the entry zone.',
        severity: 'critical',
      },
    ],
  },
]

const workerAssignments: WorkerAssignment[] = [
  {
    id: 'assignment-demo-worker',
    worker_name: 'detection-ai-worker',
    site_id: OFFICE_SITE_ID,
    site_name: 'Indore Office',
    site_type: 'office',
    camera_id: OFFICE_GATE_CAMERA_ID,
    camera_name: 'Front Gate Camera',
    camera_source_type: 'droidcam',
    camera_source: '192.168.1.44:4747',
    is_active: true,
    assignment_version: 4,
    camera_connected: true,
    frame_count: 1842,
    last_detection_count: 3,
    last_labels: ['employee', 'person', 'vehicle'],
    message: 'Local worker healthy. Running YOLOv8n, pose, YuNet, and SFace on the office gate feed.',
    frame_url: officeFrame,
    frame_updated_at: NOW,
    last_heartbeat_at: NOW,
  },
]

const liveStatusBySite: Record<string, LiveMonitorStatus> = {
  [OFFICE_SITE_ID]: {
    worker_name: 'detection-ai-worker',
    assignment_active: true,
    site_id: OFFICE_SITE_ID,
    site_name: 'Indore Office',
    camera_id: OFFICE_GATE_CAMERA_ID,
    camera_name: 'Front Gate Camera',
    camera_source_type: 'droidcam',
    camera_source: '192.168.1.44:4747',
    camera_connected: true,
    frame_updated_at: NOW,
    last_heartbeat_at: NOW,
    frame_count: 1842,
    last_detection_count: 3,
    last_labels: ['employee', 'person', 'vehicle'],
    message: 'Local worker is healthy and sending detections every second in demo mode.',
    frame_url: officeFrame,
  },
  [HOME_SITE_ID]: {
    worker_name: 'detection-ai-worker',
    assignment_active: true,
    site_id: HOME_SITE_ID,
    site_name: 'Palasia Home',
    camera_id: HOME_GATE_CAMERA_ID,
    camera_name: 'Gate Camera',
    camera_source_type: 'webcam',
    camera_source: '0',
    camera_connected: true,
    frame_updated_at: NOW,
    last_heartbeat_at: NOW,
    frame_count: 932,
    last_detection_count: 2,
    last_labels: ['known_person', 'person'],
    message: 'Demo home feed is showing how gate alerts differ for known people versus unknown visitors.',
    frame_url: homeFrame,
  },
}

function buildZoneVisits(zoneName: string, visitCount: number): EmployeeZoneVisitStat[] {
  return [{ zone_name: zoneName, visit_count: visitCount }]
}

function buildEmployeeTimeline(
  employeeName: string,
  zoneName: string,
  cameraName: string,
): EmployeeTimelineItem[] {
  return [
    {
      item_type: 'alert',
      occurred_at: '2026-04-24T10:58:00+05:30',
      title: 'Smoking Area Alert',
      description: `${employeeName} was observed in ${zoneName}.`,
      zone_name: zoneName,
      camera_name: cameraName,
      severity: 'high',
      status: 'open',
      posture: null,
      inactive_seconds: null,
    },
    {
      item_type: 'sighting',
      occurred_at: '2026-04-24T10:31:00+05:30',
      title: 'Shift Presence Detected',
      description: `${employeeName} was seen on the main floor during shift hours.`,
      zone_name: 'Main Floor',
      camera_name: cameraName,
      severity: 'low',
      status: 'recorded',
      posture: null,
      inactive_seconds: null,
    },
    {
      item_type: 'alert',
      occurred_at: '2026-04-23T16:12:00+05:30',
      title: 'Inactivity Event',
      description: `${employeeName} appeared inactive for an extended period.`,
      zone_name: 'Main Floor',
      camera_name: cameraName,
      severity: 'medium',
      status: 'reviewed',
      posture: 'inactive',
      inactive_seconds: 420,
    },
  ]
}

function buildAttendanceDays(): EmployeeAttendanceDay[] {
  return [
    {
      date: '2026-04-24',
      is_scheduled: true,
      status: 'on_time',
      first_seen_at: '2026-04-24T09:02:00+05:30',
      last_seen_at: '2026-04-24T17:11:00+05:30',
      arrival_delta_minutes: 2,
      outside_shift_sighting_count: 0,
    },
    {
      date: '2026-04-23',
      is_scheduled: true,
      status: 'late',
      first_seen_at: '2026-04-23T09:18:00+05:30',
      last_seen_at: '2026-04-23T17:04:00+05:30',
      arrival_delta_minutes: 18,
      outside_shift_sighting_count: 1,
    },
    {
      date: '2026-04-22',
      is_scheduled: true,
      status: 'on_time',
      first_seen_at: '2026-04-22T08:58:00+05:30',
      last_seen_at: '2026-04-22T17:06:00+05:30',
      arrival_delta_minutes: -2,
      outside_shift_sighting_count: 0,
    },
  ]
}

function buildDailySummaries(zoneName: string): EmployeeDaySummary[] {
  return [
    {
      date: '2026-04-24',
      first_seen_at: '2026-04-24T09:02:00+05:30',
      last_seen_at: '2026-04-24T17:11:00+05:30',
      presence_minutes: 478,
      sighting_count: 34,
      alert_count: 1,
      violation_count: 1,
      inactivity_event_count: 0,
      top_zones: buildZoneVisits(zoneName, 6),
    },
    {
      date: '2026-04-23',
      first_seen_at: '2026-04-23T09:18:00+05:30',
      last_seen_at: '2026-04-23T17:04:00+05:30',
      presence_minutes: 446,
      sighting_count: 28,
      alert_count: 1,
      violation_count: 1,
      inactivity_event_count: 1,
      top_zones: buildZoneVisits('Main Floor', 7),
    },
  ]
}

function buildEmployeeReport(employee: Employee): EmployeeReport {
  const fullName = `${employee.first_name} ${employee.last_name}`
  const zoneName = employee.id === EMPLOYEE_RIYA_ID ? 'Smoking Area' : 'Main Floor'
  const totals =
    employee.id === EMPLOYEE_RIYA_ID
      ? {
          presence_minutes: 924,
          sighting_count: 62,
          alert_count: 2,
          violation_count: 2,
          zone_visit_count: 11,
          days_observed: 3,
          inactivity_event_count: 1,
          longest_inactivity_seconds: 420,
        }
      : {
          presence_minutes: 968,
          sighting_count: 70,
          alert_count: 0,
          violation_count: 0,
          zone_visit_count: 14,
          days_observed: 3,
          inactivity_event_count: 0,
          longest_inactivity_seconds: 0,
        }

  return {
    employee: {
      id: employee.id,
      employee_code: employee.employee_code,
      full_name: fullName,
      role_title: employee.role_title,
      site_id: employee.site_id,
      site_name: 'Indore Office',
      timezone: 'Asia/Calcutta',
      shift_name: employee.shift_name,
      shift_start_time: employee.shift_start_time,
      shift_end_time: employee.shift_end_time,
      shift_grace_minutes: employee.shift_grace_minutes,
      shift_days: employee.shift_days,
      shift_crosses_midnight: false,
    },
    generated_at: NOW,
    window_start: WINDOW_START,
    window_end: NOW,
    days: 7,
    totals,
    attendance_totals: {
      scheduled_days: 3,
      attended_days: 3,
      on_time_days: 2,
      late_days: 1,
      missed_days: 0,
      off_day_activity_days: 0,
      outside_shift_sighting_count: employee.id === EMPLOYEE_RIYA_ID ? 1 : 0,
    },
    zone_visits:
      employee.id === EMPLOYEE_RIYA_ID
        ? [
            { zone_name: 'Smoking Area', visit_count: 4 },
            { zone_name: 'Main Floor', visit_count: 7 },
          ]
        : [
            { zone_name: 'Main Floor', visit_count: 9 },
            { zone_name: 'Server Room Corridor', visit_count: 2 },
          ],
    daily_summaries: buildDailySummaries(zoneName),
    attendance_days: buildAttendanceDays(),
    recent_timeline: buildEmployeeTimeline(fullName, zoneName, 'Front Gate Camera'),
  }
}

const reportsByEmployee: Record<string, EmployeeReport> = Object.fromEntries(
  employeesBySite[OFFICE_SITE_ID].map((employee) => [employee.id, buildEmployeeReport(employee)]),
)

function getSiteId(searchParams: URLSearchParams) {
  return searchParams.get('site_id') || OFFICE_SITE_ID
}

export function getDemoRestrictionMessage(path: string, method: string) {
  const action = method.toUpperCase()

  if (path.startsWith('/worker-assignments/')) {
    return 'Not allowed in demo mode. Worker assignment stays local right now because the Python CV worker needs direct access to webcam, DroidCam, or RTSP sources on the same machine or LAN. Keeping it local avoids exposing private camera endpoints, avoids constant video uplink to the cloud, and keeps real-time latency more stable.'
  }

  if (path.includes('/face-profiles')) {
    return 'Not allowed in demo mode. Face enrollment is blocked for security and privacy reasons because it would store biometric data.'
  }

  if (action === 'DELETE') {
    return 'Not allowed in demo mode. Delete actions are blocked for security reasons so recruiters can explore safely without changing real monitoring data.'
  }

  return 'Not allowed in demo mode. Write actions are blocked for security reasons so demo visitors can explore the product without changing users, sites, cameras, zones, rules, or stored data.'
}

export function getDemoApiResponse<T>(path: string): T {
  const url = new URL(path, 'http://demo.local')
  const siteId = getSiteId(url.searchParams)
  const pathname = url.pathname

  if (pathname === '/sites') {
    return structuredClone(sites) as T
  }

  if (pathname === '/admins') {
    return structuredClone(admins) as T
  }

  if (pathname === '/modes/templates') {
    return structuredClone(modeTemplates) as T
  }

  if (pathname === '/dashboard/overview') {
    return structuredClone(dashboardOverviewBySite[siteId] ?? dashboardOverviewBySite[OFFICE_SITE_ID]) as T
  }

  if (pathname === '/alerts') {
    return structuredClone(alertsBySite[siteId] ?? []) as T
  }

  if (pathname === '/cameras') {
    return structuredClone(camerasBySite[siteId] ?? []) as T
  }

  if (pathname === '/zones') {
    return structuredClone(zonesBySite[siteId] ?? []) as T
  }

  if (pathname === '/rules') {
    return structuredClone(rulesBySite[siteId] ?? []) as T
  }

  if (pathname === '/employees') {
    return structuredClone(employeesBySite[siteId] ?? []) as T
  }

  if (pathname === '/known-people') {
    return structuredClone(knownPeopleBySite[siteId] ?? []) as T
  }

  if (pathname === '/worker-assignments') {
    return structuredClone(workerAssignments) as T
  }

  if (pathname === '/live/status') {
    return structuredClone(liveStatusBySite[siteId] ?? liveStatusBySite[OFFICE_SITE_ID]) as T
  }

  const employeeReportMatch = pathname.match(/^\/employees\/([^/]+)\/report$/)
  if (employeeReportMatch) {
    const report = reportsByEmployee[employeeReportMatch[1]]
    if (!report) {
      throw new Error('Demo report is not available for this employee.')
    }

    const requestedDays = Number(url.searchParams.get('days') || report.days)
    return structuredClone({
      ...report,
      days: Number.isFinite(requestedDays) && requestedDays > 0 ? requestedDays : report.days,
    }) as T
  }

  throw new Error(`Demo data is not available for ${pathname}.`)
}
