import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import random
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, PageBreak, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime, timedelta
import os
from collections import deque, defaultdict

class SeatingPlanner:
    def __init__(self):
        self.scaler = StandardScaler()
        
    def create_student_dataset(self, classes):
        """Create a dataset of all students with their class information, excluding TC students, including LEET students"""
        students = []
        
        for cls in classes:
            class_name = cls['name']
            start_roll = int(cls['start_roll'])
            end_roll = int(cls['end_roll'])
            tc_students = cls.get('tc', '').strip()
            leet_students = cls.get('leet', '').strip()
            
            # Parse TC (Transfer/Left) students
            tc_list = []
            if tc_students:
                try:
                    tc_list = [int(x.strip()) for x in tc_students.split(',') if x.strip().isdigit()]
                except:
                    tc_list = []
            
            # Parse LEET students
            leet_list = []
            if leet_students:
                try:
                    leet_list = [int(x.strip()) for x in leet_students.split(',') if x.strip().isdigit()]
                except:
                    leet_list = []
            
            # Generate regular student records, excluding TC students
            position = 0
            for roll_no in range(start_roll, end_roll + 1):
                if roll_no not in tc_list:
                    students.append({
                        'roll_no': roll_no,
                        'class_name': class_name,
                        'class_id': hash(class_name) % 1000,
                        'position_in_class': position,
                        'is_leet': False
                    })
                    position += 1
            
            # Add LEET students
            for roll_no in leet_list:
                students.append({
                    'roll_no': roll_no,
                    'class_name': class_name,
                    'class_id': hash(class_name) % 1000,
                    'position_in_class': position,
                    'is_leet': True
                })
                position += 1
        
        return pd.DataFrame(students)
    
    def can_place_student(self, seating_grid, row, col, seat_idx, student, rows, columns, students_per_desk):
        """Check if student can be placed - ALL RULES ARE CRITICAL"""
        student_class = student['class_name']
        desk = seating_grid[row][col]
        
        # CRITICAL RULE 1: Check same desk
        for existing_student in desk:
            if existing_student is not None and existing_student['class_name'] == student_class:
                return False
        
        # CRITICAL RULE 2: Check horizontal neighbors
        if seat_idx == 0 and col > 0:
            left_desk = seating_grid[row][col - 1]
            if left_desk and len(left_desk) > 0 and left_desk[-1] is not None:
                if left_desk[-1]['class_name'] == student_class:
                    return False
        
        if seat_idx == students_per_desk - 1 and col < columns - 1:
            right_desk = seating_grid[row][col + 1]
            if right_desk and len(right_desk) > 0 and right_desk[0] is not None:
                if right_desk[0]['class_name'] == student_class:
                    return False
        
        return True
    
    def get_last_class_in_column(self, seating_grid, row, col, rows):
        """Get the class of the last placed student in this column"""
        if row == 0:
            return None
        
        prev_row = row - 1
        if prev_row >= 0:
            desk = seating_grid[prev_row][col]
            for student in desk:
                if student is not None:
                    return student['class_name']
        
        return None
    
    def get_column_class_distribution(self, seating_grid, col, rows):
        """Get the distribution of classes in a column"""
        distribution = defaultdict(int)
        for row in range(rows):
            desk = seating_grid[row][col]
            for student in desk:
                if student is not None:
                    distribution[student['class_name']] += 1
        return distribution
    
    def find_best_column_for_class(self, seating_grid, row, student_class, columns, rows, students_per_desk):
        """Find the best column to place a student from a given class"""
        column_scores = []
        
        for col in range(columns):
            desk = seating_grid[row][col]
            empty_seats = sum(1 for s in desk if s is None)
            if empty_seats == 0:
                continue
            
            score = 0
            
            last_class = self.get_last_class_in_column(seating_grid, row, col, rows)
            if last_class == student_class:
                score += 1000
            
            distribution = self.get_column_class_distribution(seating_grid, col, rows)
            class_count = distribution.get(student_class, 0)
            score += class_count * 10
            
            column_scores.append((score, col))
        
        if not column_scores:
            return None
        
        column_scores.sort(key=lambda x: x[0])
        return column_scores[0][1]
    
    def arrange_with_constraints(self, students, rows, columns, students_per_desk):
        """Smart algorithm with STRONG vertical distribution"""
        if not students or len(students) == 0:
            return [[[] for _ in range(columns)] for _ in range(rows)]
        
        total_seats = rows * columns * students_per_desk
        total_students = len(students)
        
        seating_grid = [[[] for _ in range(columns)] for _ in range(rows)]
        for row in range(rows):
            for col in range(columns):
                seating_grid[row][col] = [None] * students_per_desk
        
        class_counts = defaultdict(int)
        for student in students:
            class_counts[student['class_name']] += 1
        
        class_names = list(class_counts.keys())
        num_classes = len(class_names)
        
        if num_classes == 1:
            idx = 0
            for row in range(rows):
                for col in range(columns):
                    for seat in range(students_per_desk):
                        if idx < len(students):
                            seating_grid[row][col][seat] = students[idx]
                            idx += 1
            return seating_grid
        
        class_groups = defaultdict(list)
        for student in students:
            class_groups[student['class_name']].append(student)
        
        for class_name in class_groups:
            random.shuffle(class_groups[class_name])
        
        placed_count = 0
        max_retries = 8
        
        for attempt in range(max_retries):
            if placed_count == total_students:
                break
            
            if attempt > 0:
                print(f"Retry attempt {attempt + 1}...")
                seating_grid = [[[] for _ in range(columns)] for _ in range(rows)]
                for row in range(rows):
                    for col in range(columns):
                        seating_grid[row][col] = [None] * students_per_desk
                
                class_groups = defaultdict(list)
                shuffled_students = students.copy()
                random.shuffle(shuffled_students)
                for student in shuffled_students:
                    class_groups[student['class_name']].append(student)
                
                placed_count = 0
            
            for row in range(rows):
                classes_to_place = []
                for class_name in class_names:
                    if len(class_groups[class_name]) > 0:
                        classes_to_place.append(class_name)
                
                random.shuffle(classes_to_place)
                
                for col in range(columns):
                    for seat_idx in range(students_per_desk):
                        if placed_count >= total_students:
                            break
                        
                        placed = False
                        
                        last_class_in_col = self.get_last_class_in_column(seating_grid, row, col, rows)
                        
                        preferred_classes = [c for c in classes_to_place 
                                           if len(class_groups[c]) > 0 and c != last_class_in_col]
                        
                        if not preferred_classes:
                            preferred_classes = [c for c in classes_to_place if len(class_groups[c]) > 0]
                        
                        for try_class in preferred_classes:
                            if placed:
                                break
                            
                            if len(class_groups[try_class]) > 0:
                                for student_idx in range(min(len(class_groups[try_class]), 3)):
                                    student = class_groups[try_class][student_idx]
                                    
                                    if self.can_place_student(seating_grid, row, col, seat_idx, 
                                                             student, rows, columns, students_per_desk):
                                        seating_grid[row][col][seat_idx] = student
                                        class_groups[try_class].pop(student_idx)
                                        placed_count += 1
                                        placed = True
                                        break
                        
                        if not placed:
                            for try_class in class_names:
                                if placed:
                                    break
                                if len(class_groups[try_class]) > 0:
                                    for student_idx in range(len(class_groups[try_class])):
                                        student = class_groups[try_class][student_idx]
                                        
                                        if self.can_place_student(seating_grid, row, col, seat_idx,
                                                                 student, rows, columns, students_per_desk):
                                            seating_grid[row][col][seat_idx] = student
                                            class_groups[try_class].pop(student_idx)
                                            placed_count += 1
                                            placed = True
                                            break
        
        print(f"Placement result: {placed_count}/{total_students} students placed")
        
        if placed_count < total_students:
            print("Attempting backtracking for remaining students...")
            remaining_students = []
            for class_name in class_names:
                remaining_students.extend(class_groups[class_name])
            
            if len(remaining_students) <= 15:
                empty_positions = []
                for row in range(rows):
                    for col in range(columns):
                        for seat_idx in range(students_per_desk):
                            if seating_grid[row][col][seat_idx] is None:
                                empty_positions.append((row, col, seat_idx))
                
                success = self.try_place_remaining(seating_grid, remaining_students, empty_positions,
                                                   0, rows, columns, students_per_desk)
                if success:
                    placed_count = total_students
                    print("Backtracking successful!")
        
        return seating_grid
    
    def try_place_remaining(self, seating_grid, students, empty_positions, student_idx, 
                           rows, columns, students_per_desk):
        """Helper method for backtracking remaining students"""
        if student_idx >= len(students):
            return True
        
        student = students[student_idx]
        
        for pos_idx, (row, col, seat_idx) in enumerate(empty_positions):
            if self.can_place_student(seating_grid, row, col, seat_idx, student, 
                                     rows, columns, students_per_desk):
                seating_grid[row][col][seat_idx] = student
                
                remaining_positions = empty_positions[:pos_idx] + empty_positions[pos_idx+1:]
                if self.try_place_remaining(seating_grid, students, remaining_positions,
                                          student_idx + 1, rows, columns, students_per_desk):
                    return True
                
                seating_grid[row][col][seat_idx] = None
        
        return False
    
    def generate_arrangement(self, classes, halls):
        """Generate the complete seating arrangement"""
        try:
            students_df = self.create_student_dataset(classes)
            
            total_students = len(students_df)
            total_capacity = sum(int(h['rows']) * int(h['columns']) * int(h['students_per_desk']) 
                               for h in halls)
            
            if total_students == 0:
                return {'error': 'No students to arrange! Please check your class data.'}
            
            if total_capacity == 0:
                return {'error': 'Total hall capacity is 0! Please check your hall data.'}
            
            if total_students > total_capacity:
                return {'error': f'Not enough capacity! Students: {total_students}, Capacity: {total_capacity}'}
            
            students_df = students_df.sample(frac=1).reset_index(drop=True)
            
            result = {
                'halls': [],
                'summary': {
                    'total_students': total_students,
                    'total_capacity': total_capacity,
                    'halls_used': 0
                }
            }
            
            student_pool = students_df.to_dict('records')
            halls_used = 0
            
            for hall in halls:
                if not student_pool:
                    break
                
                halls_used += 1
                hall_name = hall['name']
                rows = int(hall['rows'])
                columns = int(hall['columns'])
                students_per_desk = int(hall['students_per_desk'])
                hall_capacity = rows * columns * students_per_desk
                
                hall_students_count = min(len(student_pool), hall_capacity)
                hall_students = student_pool[:hall_students_count]
                
                print(f"\n=== Arranging {hall_name}: {len(hall_students)} students ===")
                
                seating_grid = self.arrange_with_constraints(
                    hall_students, rows, columns, students_per_desk
                )
                
                occupied = sum(1 for row in seating_grid for desk in row for student in desk if student)
                
                print(f"Result: {occupied}/{len(hall_students)} students placed")
                
                if occupied != len(hall_students):
                    unplaced = len(hall_students) - occupied
                    return {
                        'error': f'Could not place {unplaced} students in {hall_name} while maintaining ALL seating rules.\n\n'
                                f'Suggestions:\n'
                                f'1. Add more examination halls\n'
                                f'2. Increase students per desk (if desks are large enough)\n'
                                f'3. Increase number of columns/rows\n'
                                f'4. Use 1 student per desk for maximum flexibility\n'
                                f'5. Distribute students across more halls (smaller groups per hall work better)'
                    }
                
                student_pool = student_pool[hall_students_count:]
                
                result['halls'].append({
                    'name': hall_name,
                    'rows': rows,
                    'columns': columns,
                    'students_per_desk': students_per_desk,
                    'capacity': hall_capacity,
                    'occupied': occupied,
                    'seating': seating_grid
                })
            
            result['summary']['halls_used'] = halls_used
            
            if student_pool:
                return {
                    'error': f'Could not place {len(student_pool)} students. Please add more halls or increase capacity.'
                }
            
            return result
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'error': f'Error generating arrangement: {str(e)}'}
    
    def generate_combined_seating_for_slot(self, exam_classes, classes, halls):
        """Generate combined seating arrangement for all classes having exam in the same time slot"""
        exam_class_list = [c for c in classes if c['name'] in exam_classes]
        if not exam_class_list:
            return None
        
        students_df = self.create_student_dataset(exam_class_list)
        if len(students_df) == 0:
            return None
        
        students_df = students_df.sample(frac=1).reset_index(drop=True)
        student_pool = students_df.to_dict('records')
        
        print(f"\n=== Generating Combined Seating for {len(exam_classes)} classes: {', '.join(exam_classes)} ===")
        print(f"Total students: {len(student_pool)}")
        
        exam_seating = []
        
        for hall in halls:
            if not student_pool:
                break
            
            hall_name = hall['name']
            rows = int(hall['rows'])
            columns = int(hall['columns'])
            students_per_desk = int(hall['students_per_desk'])
            hall_capacity = rows * columns * students_per_desk
            
            hall_students_count = min(len(student_pool), hall_capacity)
            hall_students = student_pool[:hall_students_count]
            
            print(f"Arranging {len(hall_students)} students in {hall_name}")
            
            seating_grid = self.arrange_with_constraints(
                hall_students, rows, columns, students_per_desk
            )
            
            occupied = sum(1 for row in seating_grid for desk in row for student in desk if student)
            
            student_pool = student_pool[hall_students_count:]
            
            exam_seating.append({
                'hall_name': hall_name,
                'rows': rows,
                'columns': columns,
                'students_per_desk': students_per_desk,
                'seating': seating_grid,
                'occupied': occupied
            })
            
            if not student_pool:
                break
        
        return exam_seating
    
    def generate_exam_schedule(self, classes, halls, teachers, class_subjects, date_mode, 
                              manual_dates, start_date, end_date, exams_per_day, invigilators_per_hall):
        """Generate complete exam schedule with dates, shifts, invigilator assignments, and combined seating"""
        try:
            # Build subject-class mapping
            subject_schedule = []
            for cs in class_subjects:
                class_name = cs['class_name']
                for subject in cs['subjects']:
                    subject_schedule.append({
                        'class_name': class_name,
                        'subject_name': subject['name'],
                        'difficulty': int(subject['difficulty'])
                    })
            
            # Sort by difficulty (hardest first)
            subject_schedule.sort(key=lambda x: x['difficulty'], reverse=True)
            
            # Generate dates with shifts
            if date_mode == 'manual':
                exam_dates = self.assign_manual_dates(subject_schedule, manual_dates)
            else:
                exam_dates = self.auto_generate_dates(subject_schedule, start_date, end_date, 
                                                     exams_per_day, classes)
            
            # Group exams by date and shift (time slot)
            exams_by_slot = defaultdict(list)
            for exam in exam_dates:
                slot_key = f"{exam['date']}_{exam['shift']}"
                exams_by_slot[slot_key].append(exam)
            
            # Generate SINGLE combined seating for each time slot
            slot_seating = {}
            for slot_key, slot_exams in exams_by_slot.items():
                exam_classes = list(set(exam['class_name'] for exam in slot_exams))
                combined_seating = self.generate_combined_seating_for_slot(exam_classes, classes, halls)
                slot_seating[slot_key] = {
                    'seating': combined_seating,
                    'exam_classes': exam_classes
                }
            
            # Assign halls and invigilators ensuring one teacher per hall per slot
            schedule_with_assignments = self.assign_halls_and_invigilators_smart(
                exam_dates, slot_seating, halls, teachers, invigilators_per_hall
            )
            
            return {
                'exam_schedule': schedule_with_assignments,
                'summary': {
                    'total_exams': len(subject_schedule),
                    'total_days': len(set(e['date'] for e in schedule_with_assignments)),
                    'halls_used': len(halls),
                    'teachers_assigned': len(teachers)
                }
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'error': f'Error generating exam schedule: {str(e)}'}
    
    def assign_manual_dates(self, subject_schedule, manual_dates):
        """Assign manually provided dates and shifts to exams"""
        exam_dates = []
        for exam in subject_schedule:
            key = f"{exam['class_name']}_{exam['subject_name']}"
            date_shift = manual_dates.get(key, {})
            date = date_shift.get('date', 'Not Assigned')
            shift = date_shift.get('shift', 'Morning')
            exam_dates.append({
                'class_name': exam['class_name'],
                'subject_name': exam['subject_name'],
                'difficulty': exam['difficulty'],
                'date': date,
                'shift': shift
            })
        return exam_dates
    
    def auto_generate_dates(self, subject_schedule, start_date, end_date, exams_per_day, classes):
        """Auto-generate exam dates with shifts ensuring no class has multiple exams in same shift"""
        from datetime import datetime, timedelta
        
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        shifts = ['Morning'] if exams_per_day == 1 else ['Morning', 'Evening']
        
        exam_dates = []
        current_date = start
        shift_idx = 0
        
        remaining_exams = subject_schedule.copy()
        classes_scheduled_in_slot = set()
        
        while remaining_exams and current_date <= end:
            current_shift = shifts[shift_idx]
            scheduled_this_iteration = False
            
            for exam in remaining_exams[:]:
                if exam['class_name'] in classes_scheduled_in_slot:
                    continue
                
                exam_dates.append({
                    'class_name': exam['class_name'],
                    'subject_name': exam['subject_name'],
                    'difficulty': exam['difficulty'],
                    'date': current_date.strftime('%Y-%m-%d'),
                    'shift': current_shift
                })
                
                classes_scheduled_in_slot.add(exam['class_name'])
                remaining_exams.remove(exam)
                scheduled_this_iteration = True
                
                if len(classes_scheduled_in_slot) >= len(set(e['class_name'] for e in subject_schedule)):
                    break
            
            # Move to next shift or day
            shift_idx += 1
            if shift_idx >= len(shifts):
                shift_idx = 0
                current_date += timedelta(days=1)
                classes_scheduled_in_slot = set()
            else:
                classes_scheduled_in_slot = set()
        
        return exam_dates
    
    def assign_halls_and_invigilators_smart(self, exam_dates, slot_seating, halls, teachers, invigilators_per_hall):
        """Assign halls and invigilators ensuring ONE teacher per hall per time slot"""
        teacher_subjects = {}
        for teacher in teachers:
            teacher_subjects[teacher['name']] = teacher['subject']
        
        # Group exams by date and shift
        exams_by_slot = defaultdict(list)
        for exam in exam_dates:
            slot_key = f"{exam['date']}_{exam['shift']}"
            exams_by_slot[slot_key].append(exam)
        
        schedule_with_assignments = []
        
        for slot_key, slot_exams in sorted(exams_by_slot.items()):
            date, shift = slot_key.split('_')
            
            # Get the SINGLE combined seating for this slot
            slot_data = slot_seating.get(slot_key, {})
            combined_seating = slot_data.get('seating', [])
            exam_classes = slot_data.get('exam_classes', [])
            
            # Get subjects being examined in this slot (for teacher exclusion)
            slot_subjects = set(exam['subject_name'] for exam in slot_exams)
            
            # Find teachers who don't teach any of the subjects in this slot
            eligible_teachers = [
                t['name'] for t in teachers 
                if teacher_subjects.get(t['name'], '') not in slot_subjects
            ]
            
            # Assign teachers to halls (one teacher can only be in one hall)
            halls_with_students = [h for h in combined_seating if h['occupied'] > 0] if combined_seating else []
            num_halls_needed = len(halls_with_students)
            
            # Distribute eligible teachers across halls
            hall_invigilators = {}
            teacher_idx = 0
            for hall_idx, hall_data in enumerate(halls_with_students):
                hall_name = hall_data['hall_name']
                hall_teachers = []
                
                for _ in range(invigilators_per_hall):
                    if teacher_idx < len(eligible_teachers):
                        hall_teachers.append(eligible_teachers[teacher_idx])
                        teacher_idx += 1
                
                hall_invigilators[hall_name] = hall_teachers
            
            # Create exam entries for each subject in this slot
            for exam in slot_exams:
                # Find which hall this exam is in (based on seating)
                assigned_hall = halls_with_students[0]['hall_name'] if halls_with_students else halls[0]['name']
                assigned_invigilators = hall_invigilators.get(assigned_hall, [])
                
                schedule_with_assignments.append({
                    'date': date,
                    'shift': shift,
                    'class_name': exam['class_name'],
                    'subject_name': exam['subject_name'],
                    'difficulty': exam['difficulty'],
                    'hall_name': assigned_hall,
                    'hall_capacity': halls_with_students[0]['occupied'] if halls_with_students else 0,
                    'invigilators': assigned_invigilators,
                    'seating_arrangement': combined_seating,
                    'exam_classes_in_slot': exam_classes,
                    'slot_key': slot_key
                })
        
        return schedule_with_assignments
    
    def generate_pdf(self, arrangement):
        """Generate seating arrangement PDF"""
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from datetime import datetime

        LEFT_MARGIN = RIGHT_MARGIN = TOP_MARGIN = BOTTOM_MARGIN = 36
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = f"output/seating_arrangement_{timestamp}.pdf"

        page_width, _ = landscape(A4)
        usable_width = page_width - (LEFT_MARGIN + RIGHT_MARGIN)

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=landscape(A4),
            rightMargin=RIGHT_MARGIN,
            leftMargin=LEFT_MARGIN,
            topMargin=TOP_MARGIN,
            bottomMargin=BOTTOM_MARGIN
        )

        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'Title',
            fontSize=30,
            leading=38,
            textColor=colors.HexColor("#0d47a1"),
            alignment=1,
            fontName="Helvetica-Bold",
            spaceAfter=12
        )
        subtitle_style = ParagraphStyle(
            'Subtitle',
            fontSize=15,
            leading=22,
            textColor=colors.HexColor("#283593"),
            alignment=1,
            fontName="Helvetica-Bold",
            spaceAfter=35
        )

        elements.append(Paragraph("Examination Seating Arrangement", title_style))
        elements.append(Spacer(1, 0.15 * inch))
        elements.append(Paragraph("AI-Generated Hall-wise Seating Layout", subtitle_style))
        elements.append(Spacer(1, 0.25 * inch))

        summary = arrangement.get("summary", {})
        summary_data = [
            ["Total Students", str(summary.get("total_students", 0))],
            ["Total Capacity", str(summary.get("total_capacity", 0))],
            ["Halls Used", str(summary.get("halls_used", 0))],
            ["Generated On", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
        ]
        summary_table = Table(summary_data, colWidths=[usable_width / 4, usable_width / 4])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e3f2fd")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#90caf9")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.4 * inch))

        row_label_style = ParagraphStyle('RowLabel', fontSize=10, leading=13, alignment=1, fontName="Helvetica-Bold")
        cell_style = ParagraphStyle('Cell', fontSize=10, leading=13, alignment=1)
        class_style = ParagraphStyle('ClassCell', fontSize=10, leading=13, alignment=1, textColor=colors.HexColor("#1e88e5"))
        empty_style = ParagraphStyle('EmptyCell', fontSize=10, leading=13, alignment=1, textColor=colors.HexColor("#9e9e9e"))

        for hall in arrangement.get("halls", []):
            hall_name = hall["name"]
            seating = hall["seating"]
            rows = len(seating)
            cols = len(seating[0]) if rows > 0 else 0

            hall_banner = Table([[f"{hall_name} – Capacity: {hall['capacity']} | Occupied: {hall['occupied']}"]],
                                colWidths=[usable_width])
            hall_banner.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1565c0")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 14),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            elements.append(hall_banner)
            elements.append(Spacer(1, 0.2 * inch))

            table_data = [[""] + [f"Col {i + 1}" for i in range(cols)]]

            for r_idx, row in enumerate(seating):
                row_cells = [Paragraph(f"Row {r_idx + 1}", row_label_style)]
                for desk in row:
                    if all(s is None for s in desk):
                        row_cells.append(Paragraph("Empty", empty_style))
                        continue

                    parts = []
                    for student in desk:
                        if student:
                            leet_marker = " [LEET]" if student.get("is_leet", False) else ""
                            parts.append(f"<b>{student['roll_no']}</b> (<font color='#1e88e5'>{student['class_name']}</font>){leet_marker}")
                        else:
                            parts.append("<font color='#9e9e9e'><i>Empty</i></font>")
                    row_cells.append(Paragraph(" | ".join(parts), class_style))
                table_data.append(row_cells)

            row_label_col = 1.0 * inch
            per_col = max((usable_width - row_label_col) / max(cols, 1), 1.4 * inch)
            if (row_label_col + per_col * cols) > usable_width:
                per_col = (usable_width - row_label_col) / max(cols, 1)
            col_widths = [row_label_col] + [per_col] * cols

            seating_table = Table(table_data, colWidths=col_widths, repeatRows=1)

            style = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d47a1")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 11),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ("TOPPADDING", (0, 0), (-1, 0), 10),

                ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#e3f2fd")),
                ("TEXTCOLOR", (0, 1), (0, -1), colors.HexColor("#0d47a1")),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),

                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#90caf9")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (1, 1), (-1, -1), 8),
                ("BOTTOMPADDING", (1, 1), (-1, -1), 8),
                ("FONTSIZE", (1, 1), (-1, -1), 10),
            ]

            for i in range(1, len(table_data)):
                bg_color = colors.HexColor("#f8fbff") if i % 2 == 0 else colors.white
                style.append(("BACKGROUND", (1, i), (-1, i), bg_color))

            seating_table.setStyle(TableStyle(style))
            elements.append(seating_table)
            elements.append(Spacer(1, 0.4 * inch))
            elements.append(PageBreak())

        doc.build(elements)
        return pdf_path
    
    def generate_exam_schedule_pdf(self, exam_schedule_data):
        """Generate comprehensive exam schedule PDF with ONE seating arrangement per time slot"""
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from datetime import datetime
        from collections import defaultdict

        LEFT_MARGIN = RIGHT_MARGIN = TOP_MARGIN = BOTTOM_MARGIN = 36
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = f"output/exam_schedule_{timestamp}.pdf"

        page_width, _ = landscape(A4)
        usable_width = page_width - (LEFT_MARGIN + RIGHT_MARGIN)

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=landscape(A4),
            rightMargin=RIGHT_MARGIN,
            leftMargin=LEFT_MARGIN,
            topMargin=TOP_MARGIN,
            bottomMargin=BOTTOM_MARGIN
        )

        elements = []

        title_style = ParagraphStyle(
            'Title',
            fontSize=32,
            leading=40,
            textColor=colors.HexColor("#0d47a1"),
            alignment=1,
            fontName="Helvetica-Bold",
            spaceAfter=15
        )
        subtitle_style = ParagraphStyle(
            'Subtitle',
            fontSize=16,
            leading=24,
            textColor=colors.HexColor("#283593"),
            alignment=1,
            fontName="Helvetica-Bold",
            spaceAfter=30
        )
        section_style = ParagraphStyle(
            'Section',
            fontSize=20,
            leading=28,
            textColor=colors.HexColor("#1565c0"),
            alignment=1,
            fontName="Helvetica-Bold",
            spaceAfter=20
        )

        # Title Page
        elements.append(Paragraph("Examination Schedule", title_style))
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(Paragraph("Complete Datesheet & Seating Plan with Invigilators", subtitle_style))
        elements.append(Spacer(1, 0.4 * inch))

        # Summary
        summary = exam_schedule_data.get("summary", {})
        summary_data = [
            ["Total Exams", str(summary.get("total_exams", 0))],
            ["Total Days", str(summary.get("total_days", 0))],
            ["Halls Used", str(summary.get("halls_used", 0))],
            ["Teachers Assigned", str(summary.get("teachers_assigned", 0))],
            ["Generated On", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
        ]
        summary_table = Table(summary_data, colWidths=[usable_width / 3, usable_width / 3])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e3f2fd")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 12),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#90caf9")),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.5 * inch))
        elements.append(PageBreak())

        # Datesheet Section
        elements.append(Paragraph("Examination Datesheet", section_style))
        elements.append(Spacer(1, 0.3 * inch))

        schedule = exam_schedule_data.get("exam_schedule", [])
        
        # Group by slot
        exams_by_slot = defaultdict(list)
        for exam in schedule:
            slot_key = exam.get('slot_key', f"{exam['date']}_{exam.get('shift', 'Morning')}")
            exams_by_slot[slot_key].append(exam)

        datesheet_data = [["Date", "Shift", "Class", "Subject", "Hall", "Difficulty", "Invigilators"]]
        
        for slot_key in sorted(exams_by_slot.keys()):
            exams = exams_by_slot[slot_key]
            for exam in exams:
                invigilators_str = ", ".join(exam.get('invigilators', []))
                difficulty_stars = "★" * exam.get('difficulty', 1)
                datesheet_data.append([
                    exam['date'],
                    exam.get('shift', 'Morning'),
                    exam['class_name'],
                    exam['subject_name'],
                    exam['hall_name'],
                    difficulty_stars,
                    invigilators_str
                ])

        col_widths = [1.0*inch, 0.8*inch, 0.9*inch, 1.2*inch, 0.9*inch, 0.7*inch, 2.3*inch]
        datesheet_table = Table(datesheet_data, colWidths=col_widths, repeatRows=1)
        
        datesheet_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1565c0")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#90caf9")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
        ]
        
        for i in range(1, len(datesheet_data)):
            bg_color = colors.HexColor("#f0f8ff") if i % 2 == 0 else colors.white
            datesheet_style.append(("BACKGROUND", (0, i), (-1, i), bg_color))
        
        datesheet_table.setStyle(TableStyle(datesheet_style))
        elements.append(datesheet_table)
        elements.append(Spacer(1, 0.5 * inch))
        elements.append(PageBreak())

        # Detailed Schedule by Time Slot with SINGLE Seating Arrangement
        elements.append(Paragraph("Detailed Examination Schedule with Seating Arrangements", section_style))
        elements.append(Spacer(1, 0.3 * inch))

        row_label_style = ParagraphStyle('RowLabel', fontSize=9, leading=11, alignment=1, fontName="Helvetica-Bold")
        cell_style = ParagraphStyle('Cell', fontSize=8, leading=10, alignment=1)

        # Process each unique time slot (date + shift)
        processed_slots = set()
        
        for slot_key in sorted(exams_by_slot.keys()):
            if slot_key in processed_slots:
                continue
            processed_slots.add(slot_key)
            
            exams = exams_by_slot[slot_key]
            first_exam = exams[0]
            date = first_exam['date']
            shift = first_exam.get('shift', 'Morning')
            
            # Slot Banner
            slot_banner = Table([[f"Date: {date} | Shift: {shift}"]],
                                colWidths=[usable_width])
            slot_banner.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0d47a1")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 16),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]))
            elements.append(slot_banner)
            elements.append(Spacer(1, 0.2 * inch))

            # List all exams in this slot
            exam_classes_in_slot = first_exam.get('exam_classes_in_slot', [first_exam['class_name']])
            
            elements.append(Paragraph(
                f"<b>Classes with Exams:</b> {', '.join(exam_classes_in_slot)}", 
                ParagraphStyle('ClassesList', fontSize=11, leading=14, 
                             textColor=colors.HexColor("#1565c0"), fontName="Helvetica-Bold")))
            elements.append(Spacer(1, 0.15 * inch))

            # Show all subject-class combinations
            exam_info = []
            for exam in exams:
                exam_info.append(f"• {exam['class_name']}: {exam['subject_name']} (Difficulty: {'★' * exam.get('difficulty', 1)})")
            
            exam_info_text = "<br/>".join(exam_info)
            elements.append(Paragraph(exam_info_text, 
                ParagraphStyle('ExamInfo', fontSize=10, leading=13, textColor=colors.black)))
            elements.append(Spacer(1, 0.2 * inch))

            # Get SINGLE combined seating arrangement for this slot
            seating_arrangement = first_exam.get('seating_arrangement', [])
            
            if seating_arrangement:
                # Show hall assignments with invigilators
                elements.append(Paragraph("<b>Hall Assignments & Invigilators:</b>", 
                    ParagraphStyle('HallHeader', fontSize=12, leading=16, 
                                 textColor=colors.HexColor("#1565c0"), fontName="Helvetica-Bold")))
                elements.append(Spacer(1, 0.1 * inch))
                
                # Group halls and show their invigilators
                hall_invigilator_data = [["Hall", "Invigilators", "Students"]]
                halls_seen = set()
                
                for exam in exams:
                    hall_name = exam['hall_name']
                    if hall_name not in halls_seen:
                        halls_seen.add(hall_name)
                        invigilators = ", ".join(exam.get('invigilators', []))
                        capacity = exam.get('hall_capacity', 0)
                        hall_invigilator_data.append([hall_name, invigilators, str(capacity)])
                
                hall_table = Table(hall_invigilator_data, colWidths=[1.5*inch, 4*inch, 1*inch])
                hall_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1565c0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#90caf9")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f0f8ff")),
                ]))
                elements.append(hall_table)
                elements.append(Spacer(1, 0.2 * inch))
                
                # Add combined seating note
                if len(exam_classes_in_slot) > 1:
                    combined_note = Paragraph(
                        f"<b>COMBINED SEATING ARRANGEMENT</b><br/>"
                        f"<i>Students from {', '.join(exam_classes_in_slot)} are seated together following anti-copying rules</i>", 
                        ParagraphStyle('CombinedNote', fontSize=11, leading=14, 
                                     textColor=colors.HexColor("#d32f2f"), fontName="Helvetica-Bold"))
                    elements.append(combined_note)
                    elements.append(Spacer(1, 0.15 * inch))
                
                elements.append(Paragraph("<b>Seating Arrangement:</b>", 
                    ParagraphStyle('SeatingHeader', fontSize=12, leading=16, 
                                 textColor=colors.HexColor("#1565c0"), fontName="Helvetica-Bold")))
                elements.append(Spacer(1, 0.1 * inch))
                
                for hall_seating in seating_arrangement:
                    hall_name = hall_seating['hall_name']
                    seating = hall_seating['seating']
                    rows = hall_seating['rows']
                    cols = hall_seating['columns']
                    occupied = hall_seating['occupied']
                    
                    # Hall subtitle
                    hall_subtitle = Paragraph(f"<b>{hall_name}</b> - Occupied: {occupied}", 
                        ParagraphStyle('HallSubtitle', fontSize=11, leading=14, 
                                     textColor=colors.HexColor("#283593"), fontName="Helvetica-Bold"))
                    elements.append(hall_subtitle)
                    elements.append(Spacer(1, 0.1 * inch))
                    
                    # Seating table
                    table_data = [[""] + [f"C{i + 1}" for i in range(cols)]]
                    
                    for r_idx, row in enumerate(seating):
                        row_cells = [Paragraph(f"R{r_idx + 1}", row_label_style)]
                        for desk in row:
                            if all(s is None for s in desk):
                                row_cells.append(Paragraph("-", cell_style))
                                continue
                            
                            parts = []
                            for student in desk:
                                if student:
                                    leet_marker = "[L]" if student.get("is_leet", False) else ""
                                    class_name = student['class_name']
                                    parts.append(f"<b>{student['roll_no']}</b> <font color='#1565c0' size='7'>({class_name})</font>{leet_marker}")
                                else:
                                    parts.append("-")
                            row_cells.append(Paragraph(" | ".join(parts), cell_style))
                        table_data.append(row_cells)
                    
                    row_label_col = 0.5 * inch
                    per_col = (usable_width - row_label_col) / max(cols, 1)
                    if per_col < 0.7 * inch:
                        per_col = 0.7 * inch
                    col_widths = [row_label_col] + [per_col] * cols
                    
                    seating_table = Table(table_data, colWidths=col_widths, repeatRows=1)
                    
                    style = [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1565c0")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 9),
                        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                        
                        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#e3f2fd")),
                        ("TEXTCOLOR", (0, 1), (0, -1), colors.HexColor("#0d47a1")),
                        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                        ("ALIGN", (0, 1), (0, -1), "CENTER"),
                        
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#90caf9")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("FONTSIZE", (1, 1), (-1, -1), 8),
                    ]
                    
                    for i in range(1, len(table_data)):
                        bg_color = colors.HexColor("#f8fbff") if i % 2 == 0 else colors.white
                        style.append(("BACKGROUND", (1, i), (-1, i), bg_color))
                    
                    seating_table.setStyle(TableStyle(style))
                    elements.append(seating_table)
                    elements.append(Spacer(1, 0.2 * inch))
            else:
                elements.append(Paragraph("<i>No seating arrangement available</i>", 
                    ParagraphStyle('NoSeating', fontSize=10, leading=14, 
                                 textColor=colors.HexColor("#999999"), fontName="Helvetica-Oblique")))
                elements.append(Spacer(1, 0.1 * inch))

            elements.append(Spacer(1, 0.3 * inch))
            elements.append(PageBreak())

        doc.build(elements)
        return pdf_path