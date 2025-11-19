"""Tests for the draw system with database-backed ticket tracking."""
import io

import pytest


def upload_csv(client):
    """Helper to upload a CSV with test students."""
    csv_content = 'Student ID,Last,Preferred,Grade,Advisor,House,Clan\n'
    csv_content += '101,Smith,Alice,9,Adams,Barn,Alpha\n'
    csv_content += '102,Jones,Bob,10,Baker,Hall,Beta\n'
    csv_content += '103,Brown,Charlie,9,Clark,Barn,Gamma\n'
    csv_content += '104,Davis,Diana,11,Dean,Hall,Delta\n'
    csv_content += '105,Wilson,Eve,10,Edwards,Barn,Alpha\n'
    data = {'file': (io.BytesIO(csv_content.encode('utf-8')), 'students.csv')}
    return client.post('/api/csv/upload', data=data, content_type='multipart/form-data')


class TestTicketEarning:
    """Test ticket earning and tracking."""

    def test_clean_plate_earns_one_ticket(self, client, login):
        """When a student gets a clean plate, they earn 1 ticket."""
        login()
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'ticket_test_1'})
        
        # Get session ID
        status = client.get('/api/session/status').get_json()
        session_id = status['session_id']
        
        # Record clean plate
        response = client.post('/api/record/clean', json={'input_value': '101'})
        assert response.status_code == 200
        
        # Check draw summary - student should have 1 ticket
        draw_summary = client.get(f'/api/session/{session_id}/draw/summary')
        assert draw_summary.status_code == 200
        data = draw_summary.get_json()
        
        candidates = data['candidates']
        assert len(candidates) == 1
        assert candidates[0]['student_identifier'] == '101'
        assert candidates[0]['tickets'] == 1.0
        assert candidates[0]['probability'] == 100.0

    def test_multiple_clean_plates_accumulate_tickets(self, client, login):
        """Students accumulate tickets with multiple clean plates across sessions."""
        login()
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'ticket_test_2'})
        
        status = client.get('/api/session/status').get_json()
        session_id = status['session_id']
        
        # Record multiple clean plates for same student
        client.post('/api/record/clean', json={'input_value': '101'})
        
        # Create new session to record again
        client.post('/api/session/create', json={'session_name': 'ticket_test_3'})
        client.post('/api/record/clean', json={'input_value': '101'})
        
        # Check second session - should have cumulative tickets
        status = client.get('/api/session/status').get_json()
        session_id_2 = status['session_id']
        
        draw_summary = client.get(f'/api/session/{session_id_2}/draw/summary')
        data = draw_summary.get_json()
        
        # Student should have 2 tickets (cumulative across sessions)
        candidates = data['candidates']
        alice = next((c for c in candidates if c['student_identifier'] == '101'), None)
        assert alice is not None
        assert alice['tickets'] == 2.0

    def test_red_plate_resets_tickets_to_zero(self, client, login):
        """Red plate resets a student's tickets to 0."""
        login()
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'red_test'})
        
        status = client.get('/api/session/status').get_json()
        session_id = status['session_id']
        
        # Give student clean plates first
        client.post('/api/record/clean', json={'input_value': '101'})
        
        # Verify they have ticket
        draw_summary = client.get(f'/api/session/{session_id}/draw/summary')
        data = draw_summary.get_json()
        assert len(data['candidates']) == 1
        assert data['candidates'][0]['tickets'] == 1.0
        
        # Now give them a red plate in new session
        client.post('/api/session/create', json={'session_name': 'red_test_2'})
        status = client.get('/api/session/status').get_json()
        session_id_2 = status['session_id']
        
        client.post('/api/record/red', json={'input_value': '101'})
        
        # Check they have no tickets now
        draw_summary = client.get(f'/api/session/{session_id_2}/draw/summary')
        data = draw_summary.get_json()
        
        # Student should not appear in candidates (0 tickets)
        alice = next((c for c in data['candidates'] if c['student_identifier'] == '101'), None)
        assert alice is None or alice['tickets'] == 0.0

    def test_multiple_students_with_different_tickets(self, client, login):
        """Multiple students can have different ticket counts."""
        login()
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'multi_test'})
        
        status = client.get('/api/session/status').get_json()
        session_id = status['session_id']
        
        # Give different students clean plates
        client.post('/api/record/clean', json={'input_value': '101'})  # Alice: 1 ticket
        client.post('/api/record/clean', json={'input_value': '102'})  # Bob: 1 ticket
        client.post('/api/record/clean', json={'input_value': '103'})  # Charlie: 1 ticket
        
        draw_summary = client.get(f'/api/session/{session_id}/draw/summary')
        data = draw_summary.get_json()
        
        assert len(data['candidates']) == 3
        assert data['total_tickets'] == 3.0
        
        # Each should have equal probability
        for candidate in data['candidates']:
            assert candidate['tickets'] == 1.0
            assert abs(candidate['probability'] - 33.333) < 0.1

    def test_student_without_clean_in_session_not_eligible(self, client, login):
        """Students with no clean record in session are excluded even with tickets."""
        login()
        upload_csv(client)

        # Session 1: Alice earns one ticket
        client.post('/api/session/create', json={'session_name': 'eligibility_session_1'})
        client.post('/api/record/clean', json={'input_value': '101'})

        # Session 2: No clean entry for Alice
        client.post('/api/session/create', json={'session_name': 'eligibility_session_2'})
        status = client.get('/api/session/status').get_json()
        session_id_2 = status['session_id']

        draw_summary = client.get(f'/api/session/{session_id_2}/draw/summary').get_json()
        candidates = draw_summary['candidates']

        # Alice should not appear despite holding prior tickets
        alice = next((c for c in candidates if c['student_identifier'] == '101'), None)
        assert alice is None


class TestDrawOperations:
    """Test draw, override, finalize, and restore operations."""

    def test_draw_selects_winner(self, client, login):
        """Admin can perform a weighted random draw."""
        login()
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'draw_test'})
        
        status = client.get('/api/session/status').get_json()
        session_id = status['session_id']
        
        # Give students tickets
        client.post('/api/record/clean', json={'input_value': '101'})
        client.post('/api/record/clean', json={'input_value': '102'})
        
        # Perform draw
        draw_response = client.post(f'/api/session/{session_id}/draw/start')
        assert draw_response.status_code == 200
        
        data = draw_response.get_json()
        assert data['status'] == 'success'
        assert 'winner' in data
        assert data['winner']['student_identifier'] in ['101', '102']
        assert data['pool_size'] == 2

    def test_draw_winner_removed_from_pool_after_win(self, client, login):
        """Winner's tickets reset immediately after draw selection."""
        login()
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'winner_reset_test'})

        status = client.get('/api/session/status').get_json()
        session_id = status['session_id']

        # Single candidate guarantees deterministic winner
        client.post('/api/record/clean', json={'input_value': '101'})

        draw_response = client.post(f'/api/session/{session_id}/draw/start')
        assert draw_response.status_code == 200

        # After winning, candidate list should now be empty (tickets reset)
        finalize_response = client.post(f'/api/session/{session_id}/draw/finalize')
        assert finalize_response.status_code == 200

        summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
        remaining = summary['candidates']
        assert all(candidate['student_identifier'] != '101' for candidate in remaining)
        assert not remaining  # Only winner had tickets, so list should be empty

    def test_draw_fails_without_eligible_students(self, client, login):
        """Draw fails when no students have tickets."""
        login()
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'empty_draw'})
        
        status = client.get('/api/session/status').get_json()
        session_id = status['session_id']
        
        # Don't record any clean plates
        draw_response = client.post(f'/api/session/{session_id}/draw/start')
        assert draw_response.status_code == 400

    def test_override_allows_superadmin_to_pick_winner(self, client, login):
        """Super admin can override and pick a specific winner."""
        # Login as superadmin
        login(username='antineutrino', password='b-decay')
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'override_test'})
        
        status = client.get('/api/session/status').get_json()
        session_id = status['session_id']
        
        # Give students tickets
        client.post('/api/record/clean', json={'input_value': '101'})
        client.post('/api/record/clean', json={'input_value': '102'})
        
        # Override to pick specific student
        override_response = client.post(
            f'/api/session/{session_id}/draw/override',
            json={'student_identifier': '101'}
        )
        assert override_response.status_code == 200
        
        data = override_response.get_json()
        assert data['status'] == 'success'
        assert data['override'] is True
        assert data['winner']['student_identifier'] == '101'

        # Override winner should no longer hold tickets after reset
        summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
        print(summary)
        remaining = summary['candidates']
        assert all(candidate['student_identifier'] != '101' for candidate in remaining)
        assert any(candidate['student_identifier'] == '102' for candidate in remaining)

    def test_finalize_resets_winner_tickets(self, client, login):
        """Finalizing a draw resets winner's tickets to 0."""
        login()
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'finalize_test'})
        
        status = client.get('/api/session/status').get_json()
        session_id = status['session_id']
        
        # Give student tickets and perform draw
        client.post('/api/record/clean', json={'input_value': '101'})
        draw_response = client.post(f'/api/session/{session_id}/draw/start')
        assert draw_response.status_code == 200
        
        # Finalize the draw
        finalize_response = client.post(f'/api/session/{session_id}/draw/finalize')
        assert finalize_response.status_code == 200
        
        data = finalize_response.get_json()
        assert data['finalized'] is True
        
        # Create new session and check tickets
        client.post('/api/session/create', json={'session_name': 'after_finalize'})
        status = client.get('/api/session/status').get_json()
        session_id_2 = status['session_id']
        
        # Winner should have 0 tickets in new session
        draw_summary = client.get(f'/api/session/{session_id_2}/draw/summary')
        data = draw_summary.get_json()
        
        # No candidates should exist (all at 0)
        assert len(data['candidates']) == 0

    def test_reset_clears_winner(self, client, login):
        """Admin can reset a draw to clear the winner."""
        login()
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'reset_test'})
        
        status = client.get('/api/session/status').get_json()
        session_id = status['session_id']
        
        # Perform draw
        client.post('/api/record/clean', json={'input_value': '101'})
        client.post(f'/api/session/{session_id}/draw/start')
        
        # Reset the draw
        reset_response = client.post(f'/api/session/{session_id}/draw/reset')
        assert reset_response.status_code == 200
        
        data = reset_response.get_json()
        assert data['reset'] is True
        
        # Check draw summary - should have no winner
        draw_summary = client.get(f'/api/session/{session_id}/draw/summary')
        data = draw_summary.get_json()
        assert data['draw_info']['has_winner'] is False


class TestSessionDrawTracking:
    """Test that each session maintains unique draw records."""

    def test_each_session_has_unique_draw(self, client, login):
        """Each session should have its own unique draw record."""
        login()
        upload_csv(client)
        
        # Create first session and perform draw
        client.post('/api/session/create', json={'session_name': 'draw_session_1'})
        status1 = client.get('/api/session/status').get_json()
        session_id_1 = status1['session_id']
        
        client.post('/api/record/clean', json={'input_value': '101'})
        client.post(f'/api/session/{session_id_1}/draw/start')
        
        # Create second session and perform draw
        client.post('/api/session/create', json={'session_name': 'draw_session_2'})
        status2 = client.get('/api/session/status').get_json()
        session_id_2 = status2['session_id']
        
        client.post('/api/record/clean', json={'input_value': '102'})
        client.post(f'/api/session/{session_id_2}/draw/start')
        
        # Verify each session has its own draw
        summary1 = client.get(f'/api/session/{session_id_1}/draw/summary').get_json()
        summary2 = client.get(f'/api/session/{session_id_2}/draw/summary').get_json()
        
        assert summary1['draw_info']['has_winner'] is True
        assert summary2['draw_info']['has_winner'] is True
        
        # Winners should be different
        assert summary1['draw_info']['winner']['student_identifier'] == '101'
        assert summary2['draw_info']['winner']['student_identifier'] == '102'

    def test_draw_events_are_recorded(self, client, login):
        """All draw events should be recorded in session_draw_events."""
        login()
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'event_test'})
        
        status = client.get('/api/session/status').get_json()
        session_id = status['session_id']
        
        # Perform draw
        client.post('/api/record/clean', json={'input_value': '101'})
        client.post(f'/api/session/{session_id}/draw/start')
        
        # Finalize
        client.post(f'/api/session/{session_id}/draw/finalize')
        
        # Check history
        summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
        history = summary.get('history', [])
        
        # Should have at least draw and finalize events
        assert len(history) >= 2
        event_types = [event['event_type'] for event in history]
        assert 'draw' in event_types
        assert 'finalize' in event_types


class TestDraftPoolTracking:
    """Test that draft_pool maintains accurate ticket counts."""

    def test_draft_pool_updates_on_clean_plate(self, client, login):
        """draft_pool should reflect current ticket counts."""
        login()
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'pool_test'})
        
        status = client.get('/api/session/status').get_json()
        session_id = status['session_id']
        
        # Record clean plate
        client.post('/api/record/clean', json={'input_value': '101'})
        
        # Check that draft_pool is updated via draw summary
        summary = client.get(f'/api/session/{session_id}/draw/summary').get_json()
        candidates = summary['candidates']
        
        assert len(candidates) == 1
        assert candidates[0]['tickets'] == 1.0

    def test_draft_pool_resets_on_finalize(self, client, login):
        """draft_pool should reset winner's tickets after finalization."""
        login()
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'pool_finalize_test'})
        
        status = client.get('/api/session/status').get_json()
        session_id = status['session_id']
        
        # Give tickets and draw
        client.post('/api/record/clean', json={'input_value': '101'})
        client.post(f'/api/session/{session_id}/draw/start')
        client.post(f'/api/session/{session_id}/draw/finalize')
        
        # Create new session - winner should have 0 tickets
        client.post('/api/session/create', json={'session_name': 'pool_check'})
        status2 = client.get('/api/session/status').get_json()
        session_id_2 = status2['session_id']
        
        summary = client.get(f'/api/session/{session_id_2}/draw/summary').get_json()
        
        # Winner from previous session should not appear
        assert len(summary['candidates']) == 0


class TestTicketEvents:
    """Test that session_ticket_events properly tracks all ticket changes."""

    def test_clean_plate_creates_earn_event(self, client, login):
        """Recording clean plate should create an 'earn' ticket event."""
        login()
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'event_earn_test'})
        
        # Record clean plate - this should create ticket event
        response = client.post('/api/record/clean', json={'input_value': '101'})
        assert response.status_code == 200

    def test_red_plate_creates_reset_event(self, client, login):
        """Recording red plate should create a 'reset' ticket event."""
        login()
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'event_reset_test'})
        
        # Give ticket first
        client.post('/api/record/clean', json={'input_value': '101'})
        
        # Create new session and give red plate
        client.post('/api/session/create', json={'session_name': 'event_reset_test_2'})
        response = client.post('/api/record/red', json={'input_value': '101'})
        assert response.status_code == 200

    def test_finalize_creates_reset_event(self, client, login):
        """Finalizing draw should create a 'reset' ticket event for winner."""
        login()
        upload_csv(client)
        client.post('/api/session/create', json={'session_name': 'finalize_event_test'})
        
        status = client.get('/api/session/status').get_json()
        session_id = status['session_id']
        
        # Setup and finalize
        client.post('/api/record/clean', json={'input_value': '101'})
        client.post(f'/api/session/{session_id}/draw/start')
        response = client.post(f'/api/session/{session_id}/draw/finalize')
        
        assert response.status_code == 200


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
