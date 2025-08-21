# Multi-Course Support and Per-Class Admin Dashboard PRD

## Overview
This document outlines the requirements for supporting multiple courses within the JELAI platform. Each course will have a dedicated admin dashboard for teachers, allowing them to manage enrollments. Students will be able to select and access only the courses they are enrolled in.

## Goals
- Enable the platform to serve multiple courses concurrently.
- Provide teachers with individual admin dashboards per course/class.
- Allow teachers to enroll and manage students for their courses.
- Restrict student access to only their enrolled courses.
- Allow students to select which course to open from their enrollments.

## User Stories

### Teacher/Admin
- As a teacher, I want to have a dedicated admin dashboard for my course so that I can manage my class independently.
- As a teacher, I want to enroll and remove students from my course so that only authorized students can access it.
- As a teacher, I want to view a list of enrolled students and their activity within my course.

### Student
- As a student, I want to see a list of courses I am enrolled in when I log in so that I can select which course to access.
- As a student, I want to access course materials, notebooks, and resources only for the courses I am enrolled in.

## Acceptance Criteria
- [ ] Each course/class has a unique admin dashboard accessible only to its teacher(s).
- [ ] Teachers can enroll and remove students from their course via the dashboard.
- [ ] Students can only see and access courses they are enrolled in.
- [ ] Upon login, students are presented with a course selection screen listing only their enrolled courses.
- [ ] Course-specific resources, workspaces, and data are isolated per course.
- [ ] Admin dashboards display a list of enrolled students and their status/activity.
- [ ] System supports multiple courses and teachers concurrently without data leakage between courses.

## Out of Scope
- Cross-course analytics or reporting.
- Automated enrollment (e.g., via LMS integration).

## Open Questions
- How are teachers assigned to courses (self-service, admin assignment, etc.)?
- What authentication/authorization system is used for role and course management?
- Should students be able to request enrollment in new courses, or is it admin-only?

## Future Considerations
- Integration with institutional LMS for automated enrollments.
- Bulk enrollment via CSV upload.
- Course archiving and transfer of ownership.

---
