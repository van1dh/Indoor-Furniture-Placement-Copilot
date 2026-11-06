export const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

export const FURNITURE_TYPES = [
  { name: 'bed', label: 'Bed Count' },
  { name: 'desk', label: 'Desk Count' },
  { name: 'tv', label: 'TV Count' },
  { name: 'wardrobe', label: 'Wardrobe Count' },
];

// Keep in sync with MAX_PER_TYPE / MAX_NOTES_LENGTH in server/placement_generation.py
export const MAX_PER_TYPE = 4;
export const MAX_NOTES_LENGTH = 500;

// Returns an error message, or null if the form can be submitted.
export function validateForm(formData) {
  let total = 0;
  for (const { name, label } of FURNITURE_TYPES) {
    const raw = formData[name];
    const value = raw === '' ? 0 : Number(raw);
    if (!Number.isInteger(value) || value < 0 || value > MAX_PER_TYPE) {
      return `${label} must be a whole number from 0 to ${MAX_PER_TYPE}.`;
    }
    total += value;
  }
  if (total === 0) {
    return 'Add at least one piece of furniture.';
  }
  if (formData.notes.length > MAX_NOTES_LENGTH) {
    return `Notes must be at most ${MAX_NOTES_LENGTH} characters.`;
  }
  return null;
}

export async function generateLayout(formData) {
  const body = { notes: formData.notes };
  for (const { name } of FURNITURE_TYPES) {
    body[name] = formData[name] === '' ? 0 : Number(formData[name]);
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (e) {
    throw new Error(`Cannot reach the server at ${API_BASE_URL}. Is it running?`);
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `Server error (${response.status})`);
  }
  return `${API_BASE_URL}${data.imageUrl}`;
}
