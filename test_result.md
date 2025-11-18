#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: "Fix critical bug in trailing stop logic. Bot is selling contracts at 5% loss immediately after purchase instead of using the 25% initial stop-loss for 0DTE contracts. Root cause: New positions are incorrectly entering 'trailing' phase immediately instead of starting in 'initial' phase."

backend:
  - task: "Position Tracking State Management Bug Fix"
    implemented: true
    working: "NA"
    file: "/app/backend/trading_bot_service.py"
    stuck_count: 0
    priority: "critical"
    needs_retesting: true
    status_history:
      - working: false
        agent: "user"
        comment: "Bot selling contracts at 5% loss immediately after purchase. Should use 25% initial stop-loss for 0DTE contracts but appears to be using 5% trailing stop-loss instead. Positions incorrectly marked as 'trailing' phase from the start."
      - working: "NA"
        agent: "main"
        comment: "FIXED: Root cause identified - when a new position is opened with the same ticker_id as a previous position, the old tracking data (with phase='trailing' and lower remaining_quantity) was being reused. Fix implemented in lines 1181-1204: Added is_new_position detection by comparing current quantity vs tracking.remaining_quantity. If quantities don't match, it's a NEW position and fresh tracking is created with phase='initial'. This ensures each new trade starts with correct 25% stop-loss (0DTE) or 20% stop-loss (1DTE) in initial phase, then transitions to trailing phase only after hitting profit target and partial sell."

frontend:
  - task: "No frontend changes required for this fix"
    implemented: true
    working: "NA"
    file: "N/A"
    stuck_count: 0
    priority: "low"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "This bug fix is backend-only. No frontend changes needed."

metadata:
  created_by: "main_agent"
  version: "2.0"
  test_sequence: 2
  run_ui: false

test_plan:
  current_focus:
    - "Position Tracking State Management Bug Fix"
  stuck_tasks: []
  test_all: false
  test_priority: "critical_first"

agent_communication:
  - agent: "main"
    message: "🔧 CRITICAL BUG FIX IMPLEMENTED: Fixed position tracking state management in trading_bot_service.py (lines 1181-1204). Root cause: When bot opened a new position with same ticker_id as a previous position, old tracking data (phase='trailing', low remaining_quantity) was being reused instead of creating fresh tracking with phase='initial'. Fix: Added is_new_position detection logic that compares current position quantity vs tracking.remaining_quantity. If they don't match, creates new tracking entry with phase='initial'. This ensures: 1) 0DTE positions start with 25% initial stop-loss (not 5%) 2) 1DTE positions start with 20% initial stop-loss 3) Positions only enter 'trailing' phase after hitting profit target and executing partial sell. NEEDS TESTING: Please verify the bot now correctly initializes new positions in 'initial' phase with proper stop-loss percentages, and only transitions to 'trailing' phase after partial sell."