
export interface ConferenceProperties {
  allowedConferenceSolutionTypes: string[];
}

export interface DefaultReminder {
  method: string;
  minutes: number;
}

export interface NotificationSetting {
  type: string;
  method: string;
}

export interface CalendarListEntry {
  kind: string;
  etag: string;
  id: string;
  summary: string;
  description?: string;
  timeZone: string;
  colorId: string;
  backgroundColor: string;
  foregroundColor: string;
  selected: boolean;
  accessRole: string;
  defaultReminders: DefaultReminder[];
  notificationSettings?: {
    notifications: NotificationSetting[];
  };
  conferenceProperties: ConferenceProperties;
  primary?: boolean;
}
