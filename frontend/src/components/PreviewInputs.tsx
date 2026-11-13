/** Keep the distinction between recorded context and generative inputs visible. */
export function PreviewInputs() {
  return <details className="preview-inputs">
    <summary>What does this preview consider?</summary>
    <p><strong>Used for this illustration:</strong> your uploaded photo, the selected face and skin area, edit amount, and lighting setting.</p>
    <p><strong>Not used:</strong> sleep, mood, stress, social connection, product ingredients, product concentration, or duration of use. Adding a product note does not change the generated image.</p>
    <p>Your check-ins and real progress photos can help you review what changed over time. This image cannot determine what caused a change or predict a product’s results.</p>
  </details>;
}
