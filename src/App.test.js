import { render, screen } from '@testing-library/react';
import App from './App';
import { validateForm } from './api';

test('renders the welcome page', () => {
  render(<App />);
  expect(screen.getByRole('heading', { name: /indoor furniture placement copilot/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /try generation/i })).toBeInTheDocument();
});

describe('validateForm', () => {
  const base = { bed: '', desk: '', tv: '', wardrobe: '', notes: '' };

  test('accepts a valid form', () => {
    expect(validateForm({ ...base, bed: '1', desk: '2' })).toBeNull();
  });

  test('requires at least one piece of furniture', () => {
    expect(validateForm(base)).toMatch(/at least one/i);
  });

  test.each(['-1', '1.5', '5', 'abc'])('rejects count %s', (value) => {
    expect(validateForm({ ...base, bed: value })).toMatch(/bed count/i);
  });
});
