// 對應後端 GET /moodle/assignments 回傳的單筆作業
export interface MoodleAssignment {
  course_name: string
  title: string
  due_date: string
  url: string
}
