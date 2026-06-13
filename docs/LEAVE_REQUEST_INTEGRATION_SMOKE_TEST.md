# FlowPilot AI Leave Request Integration Smoke Test

Date: 2026-04-27  
Status: Step 28 completed

## 1. Step 28 completion summary
Step 28 is complete.

The Leave Request form integration slice was validated successfully:
- Leave Request form is connected to FastAPI.
- POST request worked when backend was running.
- UI showed success feedback.
- Backend-unavailable behavior was tested and handled without page crash.

## 2. Integration flow tested
Integration flow tested in this step:
- React Leave Request page -> frontend leave service -> FastAPI endpoint
- Success path: backend accepts request and returns mock created leave request payload
- Unavailable path: frontend shows an error message while page remains usable

## 3. Backend endpoint used
- POST http://127.0.0.1:8000/api/leave-requests

## 4. Frontend page tested
- http://localhost:5173/leave-requests

## 5. Files likely involved in the integration
Frontend files likely involved:
- frontend/src/pages/LeaveRequestPage.tsx
- frontend/src/services/leaveService.ts
- frontend/src/services/apiClient.ts
- frontend/src/services/index.ts
- frontend/src/data/leaveData.ts (for remaining mock sections)

Backend files likely involved:
- backend/app/main.py
- backend/app/api/leave_requests.py
- backend/app/services/leave_service.py

Note:
- This is a smoke-test traceability list for Step 28 and not a full dependency map.

## 6. Manual success-path test procedure
1. Start backend:
   - From backend/: uvicorn app.main:app --reload
2. Start frontend:
   - From frontend/: npm.cmd run dev
3. Open Leave Request page:
   - http://localhost:5173/leave-requests
4. Fill Leave Request form fields.
5. Submit the form.
6. Confirm success message appears in frontend.
7. Confirm page remains stable with no blank screen.

## 7. Network tab verification
Verified in browser Network tab:
- POST request to /api/leave-requests was observed.
- Response status was 200 when backend was running.
- Response payload contained generated mock leave request fields.

## 8. Example request body
```json
{
  "leave_type": "Annual Leave",
  "start_date": "2026-05-03",
  "end_date": "2026-05-05",
  "reason": "Family event"
}
```

## 9. Example successful response summary
POST /api/leave-requests returned HTTP 200 with a mock payload including:
- generated leave request id
- employee_id: mock_user_001
- status: pending
- created_at timestamp

Representative shape:
```json
{
  "success": true,
  "data": {
    "id": "lr_xxxx",
    "employee_id": "mock_user_001",
    "status": "pending",
    "created_at": "ISO datetime"
  }
}
```

## 10. Backend unavailable test procedure
1. Stop FastAPI backend server.
2. Keep frontend running.
3. Reload or re-open:
   - http://localhost:5173/leave-requests
4. Submit Leave Request form again.
5. Observe UI behavior and error feedback.

## 11. Confirmed fallback or error behavior
Confirmed behavior when backend was unavailable:
- Leave Request page did not crash.
- Existing mock sections remained visible.
- Error message appeared in frontend.
- No blank page.

## 12. What remains mock-only
- Leave history visualization remains mock-only.
- Manager approvals section remains mock-only.
- CRM modules remain mock-only.
- AI agent and workflow monitoring modules remain mock-only.

## 13. What is intentionally not implemented yet
- No manager approvals backend integration yet
- No CRM backend integration yet
- No real authentication yet
- No PostgreSQL integration yet
- No n8n integration yet

## 14. Recommended next step
Step 30: Add backend mock endpoints for Manager Approvals before connecting the Manager Approval page.
