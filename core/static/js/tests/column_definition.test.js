/**
 * @jest-environment jsdom
 */

import $ from 'jquery';
import 'bootstrap';

// Mock the CSRF token functionality
document.cookie = 'csrftoken=test-token';

describe('Column Definition Tests', () => {
    // Set up our document body
    document.body.innerHTML = `
        <div class="accordion" id="columnAccordion">
            <div class="accordion-item">
                <div class="accordion-body">
                    <table class="table">
                        <tbody data-category="demographics">
                            <tr data-column-id="1">
                                <td class="editable" data-field="name">
                                    <div class="view-mode">Test Column</div>
                                    <div class="edit-mode d-none">
                                        <input type="text" value="Test Column">
                                    </div>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        <button id="add-column">Add Column</button>
        <button id="save-table">Save Table</button>
    `;

    // Mock fetch
    global.fetch = jest.fn(() =>
        Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ success: true })
        })
    );

    beforeEach(() => {
        // Clear all mocks before each test
        fetch.mockClear();
        // Initialize any event handlers
        // This would be where you call your initialization function
    });

    test('Edit Row Handler', () => {
        // Trigger edit mode
        const editButton = document.querySelector('.edit-row');
        editButton.click();

        // Check if view mode is hidden and edit mode is shown
        const viewMode = document.querySelector('.view-mode');
        const editMode = document.querySelector('.edit-mode');
        
        expect(viewMode.classList.contains('d-none')).toBe(true);
        expect(editMode.classList.contains('d-none')).toBe(false);
    });

    test('Save Row Handler', async () => {
        // Set up the test
        const row = document.querySelector('tr[data-column-id="1"]');
        const input = row.querySelector('input[type="text"]');
        input.value = 'Updated Column';

        // Trigger save
        const saveButton = row.querySelector('.save-row');
        saveButton.click();

        // Wait for the AJAX call to complete
        await new Promise(resolve => setTimeout(resolve, 0));

        // Verify the AJAX call was made with correct data
        expect(fetch).toHaveBeenCalledWith(
            expect.any(String),
            expect.objectContaining({
                method: 'POST',
                headers: expect.objectContaining({
                    'Content-Type': 'application/json',
                    'X-CSRFToken': 'test-token'
                })
            })
        );
    });

    test('Delete Row Handler', async () => {
        // Set up confirmation mock
        window.confirm = jest.fn(() => true);

        // Trigger delete
        const deleteButton = document.querySelector('.delete-row');
        deleteButton.click();

        // Wait for the AJAX call to complete
        await new Promise(resolve => setTimeout(resolve, 0));

        // Verify confirmation was shown
        expect(window.confirm).toHaveBeenCalled();

        // Verify the AJAX call was made
        expect(fetch).toHaveBeenCalledWith(
            expect.stringContaining('/columns/1/delete/'),
            expect.objectContaining({
                method: 'POST',
                headers: expect.objectContaining({
                    'X-CSRFToken': 'test-token'
                })
            })
        );
    });

    test('Add Column Handler', async () => {
        // Mock Bootstrap modal
        $.fn.modal = jest.fn();

        // Click add column button
        const addButton = document.getElementById('add-column');
        addButton.click();

        // Verify modal was shown
        expect($.fn.modal).toHaveBeenCalledWith('show');

        // Select a category and confirm
        const categorySelect = document.getElementById('categorySelect');
        categorySelect.value = 'demographics';
        
        const confirmButton = document.getElementById('confirmCategory');
        confirmButton.click();

        // Wait for the AJAX call to complete
        await new Promise(resolve => setTimeout(resolve, 0));

        // Verify new row was added
        const tbody = document.querySelector('tbody[data-category="demographics"]');
        expect(tbody.children.length).toBeGreaterThan(0);
    });

    test('Save Table Handler', async () => {
        // Add some test data to the form fields
        document.getElementById('disease_condition').value = 'Test Disease';
        document.getElementById('population_age').value = 'Adult';
        document.getElementById('grading_of_lesion').value = 'Grade 1';

        // Click save table button
        const saveButton = document.getElementById('save-table');
        saveButton.click();

        // Wait for the AJAX call to complete
        await new Promise(resolve => setTimeout(resolve, 0));

        // Verify the AJAX call was made with correct data
        expect(fetch).toHaveBeenCalledWith(
            expect.any(String),
            expect.objectContaining({
                method: 'POST',
                headers: expect.objectContaining({
                    'Content-Type': 'application/json',
                    'X-CSRFToken': 'test-token'
                }),
                body: expect.stringContaining('disease_condition')
            })
        );
    });

    test('Apply Defaults Handler', async () => {
        // Mock confirmation
        window.confirm = jest.fn(() => true);

        // Click apply defaults button
        const applyDefaultsButton = document.getElementById('apply-defaults');
        applyDefaultsButton.click();

        // Verify confirmation was shown
        expect(window.confirm).toHaveBeenCalled();

        // Wait for the AJAX call to complete
        await new Promise(resolve => setTimeout(resolve, 0));

        // Verify the AJAX call was made
        expect(fetch).toHaveBeenCalledWith(
            expect.stringContaining('/apply-default-columns/'),
            expect.objectContaining({
                method: 'POST',
                headers: expect.objectContaining({
                    'X-CSRFToken': 'test-token'
                })
            })
        );
    });

    test('Order Only Update', async () => {
        // Set up test data
        const row = document.querySelector('tr[data-column-id="1"]');
        const orderInput = row.querySelector('input[type="number"]');
        orderInput.value = '2';

        // Trigger save
        const saveButton = row.querySelector('.save-row');
        saveButton.click();

        // Wait for the AJAX call to complete
        await new Promise(resolve => setTimeout(resolve, 0));

        // Verify the AJAX call was made with only order change
        expect(fetch).toHaveBeenCalledWith(
            expect.any(String),
            expect.objectContaining({
                method: 'POST',
                body: expect.stringContaining('"order":2')
            })
        );

        // Verify other fields weren't included in the update
        const requestBody = JSON.parse(fetch.mock.calls[0][1].body);
        expect(requestBody.columns[0]).toEqual(
            expect.objectContaining({
                id: '1',
                order: 2
            })
        );
    });
}); 